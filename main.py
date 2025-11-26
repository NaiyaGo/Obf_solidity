#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
import argparse
import random
import shutil
import os
from typing import List, Tuple, Dict, Any, Optional, Iterable, Callable

from solidity_parser import filesys
from solidity_parser.ast import symtab, solnodes
from obf_literal import find_string_literals_in_ast, should_obfuscate_literal, obfuscate_string_literal, modify_text_with_obfuscation, Obfuscation
from obf_controlflow import obfuscate_code_cf
from obf_layout import Match, get_grammar_tree, collect_definitions, traverse

DEAD_CODE_TEMPLATES = [
    "uint256 uselessVar = 0;",  # Simple unused variable
    "if (1 == 0) { uint256 neverUsed = 42; }",  # Conditional that never executes
    "for (uint256 i = 0; i < 0; i++) { uint256 neverIterated = i; }",  # Unreachable loop
    "require(1 == 0, 'This will never happen');",  # Impossible requirement
    "bytes32 unusedHash = keccak256(abi.encodePacked('dead_code'));",
]

def generate_dead_code() -> str:
    return random.choice(DEAD_CODE_TEMPLATES)

# =========================================================
# 基础工具：AST 迭代 & 函数体插槽扫描（顶层安全位置）
# =========================================================

def iter_ast_roots(ast_root) -> List[Any]:
    """把 loaded.ast 规范化为可迭代的根节点列表，过滤 None。"""
    if ast_root is None:
        return []
    if isinstance(ast_root, (list, tuple)):
        return [n for n in ast_root if (n is not None and hasattr(n, "get_all_children"))]
    return [ast_root] if hasattr(ast_root, "get_all_children") else []


def safe_func_name(func: solnodes.FunctionDefinition) -> str:
    """更友好的函数名显示。"""
    try:
        n = getattr(func, "name", None)
        if n is None:
            return "<anon>"
        return getattr(n, "value", str(n))
    except Exception:
        return "<anon>"


def find_block_end(source: str, open_brace_idx: int) -> int:
    """给定函数体 '{' 的索引，返回匹配的 '}' 索引；失败返回 -1。"""
    i = open_brace_idx + 1
    n = len(source)
    depth = 1
    in_line_cmt = False
    in_block_cmt = False
    in_str = False
    str_ch = ""
    escape = False
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if in_line_cmt:
            if ch == "\n":
                in_line_cmt = False
        elif in_block_cmt:
            if ch == "*" and nxt == "/":
                in_block_cmt = False
                i += 1
        elif in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == str_ch:
                in_str = False
        else:
            if ch == "/" and nxt == "/":
                in_line_cmt = True
                i += 1
            elif ch == "/" and nxt == "*":
                in_block_cmt = True
                i += 1
            elif ch in ("'", '"'):
                in_str = True
                str_ch = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def collect_top_level_slots(source: str, func: solnodes.FunctionDefinition) -> List[Tuple[int, str, int]]:
    """
    以函数体 '{' 为锚，收集“顶层安全插入点”：
    - '{' 后首个非空白位置
    - 顶层语句分号 ';' 之后的起始位置
    - 匹配的 '}' 之前（回退空白）
    返回: [(offset, indent, line_no), ...]
    """
    code_block = getattr(func, "code", None)
    if code_block is None:
        return []
    try:
        lbrace = code_block.start_buffer_index
    except Exception:
        return []

    end = find_block_end(source, lbrace)
    if end < 0:
        return []

    def _indent_at(pos: int) -> Tuple[str, int]:
        left = source[:pos]
        line_no = left.count("\n") + 1
        line_start = left.rfind("\n") + 1
        indent = left[line_start: len(left) - len(left[line_start:].lstrip())]
        return indent, line_no

    slots: List[Tuple[int, str, int]] = []

    # 1) '{' 后首插槽
    i = lbrace + 1
    while i < end and source[i] in " \t\r\n":
        i += 1
    ind, ln = _indent_at(i)
    slots.append((i, ind, ln))

    # 2) 顶层分号 ';' 后
    in_line_cmt = in_block_cmt = False
    in_str = False
    str_ch = ""
    escape = False
    depth = 1
    paren = bracket = 0
    i = lbrace + 1
    while i < end:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if in_line_cmt:
            if ch == "\n":
                in_line_cmt = False
        elif in_block_cmt:
            if ch == "*" and nxt == "/":
                in_block_cmt = False
                i += 1
        elif in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == str_ch:
                in_str = False
        else:
            if ch == "/" and nxt == "/":
                in_line_cmt = True
                i += 1
            elif ch == "/" and nxt == "*":
                in_block_cmt = True
                i += 1
            elif ch in ("'", '"'):
                in_str = True
                str_ch = ch
            elif ch == "(":
                paren += 1
            elif ch == ")":
                paren = max(paren - 1, 0)
            elif ch == "[":
                bracket += 1
            elif ch == "]":
                bracket = max(bracket - 1, 0)
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            elif ch == ";" and depth == 1 and paren == 0 and bracket == 0:
                j = i + 1
                while j < end and source[j] in " \t\r\n":
                    j += 1
                ind2, ln2 = _indent_at(j)
                slots.append((j, ind2, ln2))
        i += 1

    # 3) '}' 之前
    j = end
    while j > lbrace and source[j - 1] in " \t\r\n":
        j -= 1
    ind3, ln3 = _indent_at(j)
    slots.append((j, ind3, ln3))

    # 去重排序
    slots = sorted(set(slots), key=lambda x: x[0])
    return slots


# =========================================================
# Pass 上下文与基类
# =========================================================

@dataclass
class ModuleContext:
    """每处理一个文件，构造一个上下文；Pass 在其中读取 AST/源码并回写。"""
    project_dir: Path
    file_name: str
    vfs: Any
    sym_builder: Any
    ast_root: Any
    src: str
    meta: Dict[str, Any] = field(default_factory=dict)

    def rebuild(self, new_src: str) -> None:
        """
        将 new_src 作为当前源码，并在需要时重建 AST。
        注意：这里仅更新 self.src；如果你需要“变更后 AST”，
        建议在实际实现时重新构建 VFS/符号表并赋值给 ast_root。
        """
        self.src = new_src
        # 如需严格的“源码→AST”刷新逻辑，可在实现具体 Pass 时补上：
        #   self.vfs = filesys.VirtualFileSystem(self.project_dir, None, [])
        #   self.sym_builder = symtab.Builder2(self.vfs)
        #   self.sym_builder.process_or_find_from_base_dir(self.file_name)
        #   loaded = self.vfs.sources[self.file_name]
        #   self.ast_root = loaded.ast
        #   self.src = loaded.contents


class ObfuscationPass:
    """所有混淆 Pass 的抽象基类。"""
    name: str = "BasePass"

    def __init__(self, **kwargs):
        self.params = kwargs or {}

    def transform(self, ctx: ModuleContext) -> Tuple[str, Dict[str, Any]]:
        """
        输入 ModuleContext，输出 (new_src, metadata)。
        这里默认不做修改，仅打印提示。
        """
        print(f"[{self.name}] {ctx.project_dir / ctx.file_name}: (noop, scaffold only)")
        return ctx.src, {"changed": False}


# =========================================================
# 具体占位 Pass（未实现：仅日志 & 接口）
# =========================================================

class StringLiteralPass(ObfuscationPass):
    name = "StringLiteral"

    def transform(self, ctx: ModuleContext):
        """对字符串字面量做拆分+拼接的字面量混淆。仅复用用户脚本中的现有函数。"""
        density: float = float(self.params.get("density", 1.0))  # 允许抽样；默认全部替换

        # 兼容单/多根 AST：iter_ast_roots 已在你的框架中定义
        roots = iter_ast_roots(ctx.ast_root)

        # 收集字符串字面量（复用你的递归函数）
        literals = []
        for root in roots:
            literals.extend(find_string_literals_in_ast(root))

        # 过滤可混淆候选
        candidates = [lit for lit in literals if should_obfuscate_literal(lit)]

        # 采样并生成替换计划（复用你的 Obfuscation 与 obfuscate_string_literal）
        plan = []
        for lit in candidates:
            if random.random() <= density:
                obf_expr = obfuscate_string_literal(lit)
                plan.append(Obfuscation(
                    original_literal=lit,
                    obfuscated_expr=obf_expr,
                    start_index=lit.start_buffer_index,
                    end_index=lit.end_buffer_index
                ))

        print(f"[SCAN][{self.name}] {ctx.project_dir / ctx.file_name}: "
              f"literals={len(literals)}, candidates={len(candidates)}, plan={len(plan)}, density={density}")

        if not plan:
            return ctx.src, {"changed": False, "literals": len(literals),
                             "candidates": len(candidates), "replacements": 0}

        # 应用文本替换（复用你的 modify_text_with_obfuscation）
        new_src = modify_text_with_obfuscation(ctx.src, plan)

        # 打印逐项替换日志
        for obf in plan:
            val = obf.original_literal.value
            if isinstance(val, str) and len(val) > 40:
                preview = val[:37] + "..."
            else:
                preview = val
            print(f"[OBF][{self.name}] file={ctx.project_dir / ctx.file_name} "
                  f"range=[{obf.start_index}:{obf.end_index}] literal={preview!r}")

        return new_src, {
            "changed": True,
            "literals": len(literals),
            "candidates": len(candidates),
            "replacements": len(plan)
        }


class ControlFlowPass(ObfuscationPass):
    name = "ControlFlow"

    def transform(self, ctx: ModuleContext):
        """
        直接复用用户脚本中的 obfuscate_code() 对函数体内的 ExprStmt 做 if/else 包装。
        仅使用脚本中已有的函数/方法；不新增任何自定义工具。
        """
        density = float(self.params.get("density", 0.3))
        ast_nodes = ctx.ast_root  # 与你脚本中 obfuscate_file 的 loaded_src.ast 一致

        try:
            new_src = obfuscate_code_cf(ctx.src, ast_nodes, density=density)
        except Exception as e:
            print(f"[{self.name}] ERROR {ctx.project_dir / ctx.file_name}: {e}")
            return ctx.src, {"changed": False, "error": str(e), "density": density}

        changed = (new_src != ctx.src)
        print(f"[{self.name}] {ctx.project_dir / ctx.file_name}: density={density}, changed={changed}")
        return new_src, {"changed": changed, "density": density}


class DeadCodePass(ObfuscationPass):
    name = "DeadCode"

    def transform(self, ctx: ModuleContext) -> Tuple[str, Dict[str, Any]]:
        """
        在每个有函数体的函数中，按密度随机选择一个“顶层安全插槽”，插入一行死代码。
        - 顶层插槽来自 collect_top_level_slots(ctx.src, func)
        - 插入时处理换行与缩进；若在 '}' 前插入，则额外加一层缩进以保持块内对齐
        - 打印详细日志，便于追踪每一次修改
        """
        density: float = float(self.params.get("density", 0.3))
        INDENT_UNIT = "    "  # 4 空格

        roots = iter_ast_roots(ctx.ast_root)
        total_funcs = 0
        candidates = 0
        prepared: List[Tuple[int, str, int, solnodes.FunctionDefinition, str]] = []  # (pos, indent, line_no, func, code)

        # 统计并挑选插入目标
        for root in roots:
            for fn in root.get_all_children(lambda x: isinstance(x, solnodes.FunctionDefinition)):
                total_funcs += 1
                if getattr(fn, "code", None) is None:
                    # interface/abstract 函数没有函数体
                    continue
                slots = collect_top_level_slots(ctx.src, fn)
                if not slots:
                    continue
                candidates += 1
                if random.random() < density:
                    pos, indent, line_no = random.choice(slots)
                    dead_code = generate_dead_code()
                    prepared.append((pos, indent, line_no, fn, dead_code))

        print(f"[SCAN][{self.name}] {ctx.project_dir / ctx.file_name}: "
              f"functions={total_funcs}, with_body={candidates}, plan_inserts={len(prepared)}, density={density}")

        if not prepared:
            return ctx.src, {"changed": False, "functions": total_funcs, "candidates": candidates, "inserts": 0}

        # 逆序应用插入，避免偏移串扰
        src = ctx.src
        for pos, indent, line_no, fn, dead_code in sorted(prepared, key=lambda x: x[0], reverse=True):
            left, right = src[:pos], src[pos:]

            # 1) 若不在行首，先换行
            needs_leading_nl = (pos > 0 and src[pos - 1] != "\n")
            prefix_nl = "\n" if needs_leading_nl else ""

            # 2) 若正好插在 '}' 之前，额外加一层缩进
            extra_indent = INDENT_UNIT if (pos < len(src) and src[pos] == "}") else ""
            indent_for_insert = indent + extra_indent

            # 3) 组装插入文本：前置换行(如需) + 缩进 + 代码 + 换行 + 原缩进（保留后续行缩进）
            inserted = f"{prefix_nl}{indent_for_insert}{dead_code}\n{indent}"
            src = left + inserted + right

            # 打印日志
            fn_name = safe_func_name(fn)
            preview = dead_code.strip().replace("\n", " ")[:120]
            print(f"[OBF][{self.name}] file={ctx.project_dir / ctx.file_name} "
                  f"func={fn_name!r} offset={pos} line={line_no} -> insert: {preview}")

        # 返回新源码与元数据
        return src, {
            "changed": True,
            "functions": total_funcs,
            "candidates": candidates,
            "inserts": len(prepared),
        }



class LayoutPass(ObfuscationPass):
    name = "Layout"

    def transform(self, ctx: ModuleContext):
        """
        仅调用你 layout 脚本中已有的方法：
        - 将当前源码写入一个临时 .sol 路径（供 Node 解析）
        - 调用 layout.layout_obfuscate(ctx.src, tmp_path) 完成改名与倒序替换
        - 返回新源码与统计信息
        """
        import obf_layout as layout  # ← 改成你的 layout 脚本模块名（不带 .py）

        # 1) 把当前源码写入临时文件，供 getGrammarTree.js 解析
        tmp_path = Path(".solp_tmp") / ctx.file_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(ctx.src, encoding="utf-8")

        # 2) 直接调用你已封装好的入口（内部会：get_grammar_tree(tmp_path) → collect_definitions → traverse → 倒序替换）
        new_src, stats = layout.layout_obfuscate(ctx.src, str(tmp_path))

        changed = (new_src != ctx.src)
        print(f"[{self.name}] {ctx.project_dir / ctx.file_name}: renamed={stats.get('renamed', 0)}, changed={changed}")
        return new_src, {"changed": changed, **stats}


# =========================================================
# 管线执行 & I/O
# =========================================================

def build_context(project_dir: Path, file_name: str) -> ModuleContext:
    vfs = filesys.VirtualFileSystem(project_dir, None, [])
    builder = symtab.Builder2(vfs)
    builder.process_or_find_from_base_dir(file_name)
    loaded = vfs.sources[file_name]
    ast_root = loaded.ast
    src = loaded.contents
    return ModuleContext(
        project_dir=project_dir,
        file_name=file_name,
        vfs=vfs,
        sym_builder=builder,
        ast_root=ast_root,
        src=src,
    )


def run_pipeline_on_file(project_dir: Path, file_name: str, passes: List[ObfuscationPass]) -> str:
    ctx = build_context(project_dir, file_name)
    print(f"[PIPELINE] Begin → {project_dir / file_name}")
    current_src = ctx.src
    for p in passes:
        new_src, meta = p.transform(ctx)
        # 如果 Pass 改动了源码，刷新上下文的源码；（AST 刷新可在具体 Pass 内实现）
        if new_src != current_src:
            ctx.rebuild(new_src)
            current_src = new_src
            print(f"  └─ [{p.name}] changed=True, meta={meta}")
        else:
            print(f"  └─ [{p.name}] changed=False, meta={meta}")
    print(f"[PIPELINE] End   → {project_dir / file_name}")
    return current_src


def enumerate_sol_files(base: Path) -> Iterable[Path]:
    for root, _, files in os.walk(base):
        for f in files:
            if f.endswith(".sol"):
                yield Path(root) / f


def main():
    ap = argparse.ArgumentParser(description="Solidity Obfuscation Pipeline (scaffold)")
    ap.add_argument("--file", type=str, default='./gptcomments/TheContract.sol', help="指定单个 .sol 文件")
    ap.add_argument("--dir", type=str, default=None, help="指定目录（递归处理 .sol）")
    ap.add_argument("--out", type=str, default="./obf_output", help="输出目录")
    ap.add_argument("--enable", type=str, default="cf", help="启用的 Pass 列表（逗号分隔）：cf,dead,layout")
    ap.add_argument("--seed", type=int, default=None)
    
    ap.add_argument("--cf-density", type=float, default=0.9, help="ControlFlow 注入密度（占位）")
    ap.add_argument("--dead-density", type=float, default=0.3, help="DeadCode 注入密度（占位）")
    ap.add_argument("--literal-density", type=float, default=1.0, help="String literal obfuscation rate (0.0-1.0)")
    ap.add_argument("--layout-shuffle", type=float, default=0.0, help="Layout 重排强度（占位）")
    args = ap.parse_args()

    if not args.file and not args.dir:
        raise ValueError("必须指定 --file 或 --dir")

    if args.seed is not None:
        random.seed(args.seed)

    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 组装 Pass 列表（不实现，仅占位）
    enable = {x.strip() for x in args.enable.split(",") if x.strip()}
    passes: List[ObfuscationPass] = []
    if "cf" in enable:
        passes.append(ControlFlowPass(density=args.cf_density))
    if "dead" in enable:
        passes.append(DeadCodePass(density=args.dead_density))
    if "literal" in enable:
        passes.append(StringLiteralPass(density=args.literal_density))
    if "layout" in enable:
        passes.append(LayoutPass(shuffle=args.layout_shuffle))

    # 单文件模式
    if args.file:
        src_path = Path(args.file)
        if not src_path.name.endswith(".sol"):
            raise ValueError("指定的文件必须以 .sol 结尾")
        obf_src = run_pipeline_on_file(src_path.parent, src_path.name, passes)
        out_path = out_dir / src_path.name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(obf_src, encoding="utf-8")
        print(f"[WRITE] {out_path}")
        return

    # 目录模式
    base_dir = Path(args.dir)
    for src_file in enumerate_sol_files(base_dir):
        rel = src_file.relative_to(base_dir)
        obf_src = run_pipeline_on_file(src_file.parent, src_file.name, passes)
        out_path = out_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(obf_src, encoding="utf-8")
        print(f"[WRITE] {out_path}")

    print("=== Pipeline scaffold complete ===")


if __name__ == "__main__":
    main()