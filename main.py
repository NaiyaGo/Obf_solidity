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
from obf_deadcode import iter_ast_roots, collect_top_level_slots, generate_dead_code, safe_func_name
from obf_literal import find_string_literals_in_ast, should_obfuscate_literal, obfuscate_string_literal, modify_text_with_obfuscation, Obfuscation
from obf_controlflow import obfuscate_code_cf
from obf_layout import Match, get_grammar_tree, collect_definitions, traverse


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
        输入 ModuleContext, 输出 (new_src, metadata)。
        这里默认不做修改，仅打印提示。
        """
        print(f"[{self.name}] {ctx.project_dir / ctx.file_name}: (noop, scaffold only)")
        return ctx.src, {"changed": False}


# =========================================================
# 具体占位 Pass（未实现：仅日志 & 接口）
# =========================================================

from pathlib import Path
from solidity_parser import filesys
from solidity_parser.ast import symtab

class StringLiteralPass(ObfuscationPass):
    name = "StringLiteral"

    def transform(self, ctx: ModuleContext):
        density: float = float(self.params.get("density", 1.0))

        # 1) 用当前源码写到临时路径并重新解析（保证 AST 偏移与文本一致）
        tmp_path = Path(".solp_tmp") / ctx.file_name
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(ctx.src, encoding="utf-8")

        vfs = filesys.VirtualFileSystem(tmp_path.parent, None, [])
        builder = symtab.Builder2(vfs)
        builder.process_or_find_from_base_dir(tmp_path.name)
        loaded = vfs.sources[tmp_path.name]
        ast_root, src_code = loaded.ast, loaded.contents

        # 2) 收集字符串字面量（复用你的函数），并按 (start,end) 去重
        def _iter_roots(r):
            if r is None: return []
            if isinstance(r, (list, tuple)): return [x for x in r if x]
            return [r]

        literals = []
        for root in _iter_roots(ast_root):
            literals.extend(find_string_literals_in_ast(root))

        candidates = [lit for lit in literals if should_obfuscate_literal(lit)]

        seen = set()  # 去重集合
        plan = []
        for lit in candidates:
            key = (lit.start_buffer_index, lit.end_buffer_index)
            if key in seen:
                continue
            if random.random() <= density:
                obf_expr = obfuscate_string_literal(lit)
                plan.append(Obfuscation(
                    original_literal=lit,
                    obfuscated_expr=obf_expr,
                    start_index=lit.start_buffer_index,
                    end_index=lit.end_buffer_index
                ))
                seen.add(key)

        print(f"[SCAN][{self.name}] {ctx.project_dir / ctx.file_name}: "
              f"literals={len(literals)}, candidates={len(candidates)}, plan={len(plan)}, density={density}")

        if not plan:
            return ctx.src, {"changed": False, "literals": len(literals),
                             "candidates": len(candidates), "replacements": 0}

        # 3) 在“与 AST 一致的 src_code”上做替换，然后把新源码返回
        new_src = modify_text_with_obfuscation(src_code, plan)

        for obf in plan:
            val = obf.original_literal.value
            preview = (val[:37] + "...") if isinstance(val, str) and len(val) > 40 else val
            print(f"[OBF][{self.name}] file={ctx.project_dir / ctx.file_name} "
                  f"range=[{obf.start_index}:{obf.end_index}] literal={preview!r}")

        return new_src, {
            "changed": True,
            "literals": len(literals),
            "candidates": len(candidates),
            "replacements": len(plan),
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
        density: float = float(self.params.get("density", 0.3))
        INDENT_UNIT = "    "

        roots = iter_ast_roots(ctx.ast_root)
        total_funcs = 0
        candidates = 0
        prepared: List[Tuple[int, str, int, solnodes.FunctionDefinition, str]] = []

        for root in roots:
            for fn in root.get_all_children(lambda x: isinstance(x, solnodes.FunctionDefinition)):
                total_funcs += 1
                code_block = getattr(fn, "code", None)
                if code_block is None:
                    continue

                # 取函数体 '{' 的字符索引
                lbrace = getattr(code_block, "start_buffer_index", None)
                if lbrace is None:
                    # 某些版本用 loc.start.offset
                    try:
                        lbrace = code_block.loc.start.offset  # type: ignore[attr-defined]
                    except Exception:
                        continue  # 拿不到就跳过该函数

                slots = collect_top_level_slots(ctx.src, int(lbrace))
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

        src = ctx.src
        for pos, indent, line_no, fn, dead_code in sorted(prepared, key=lambda x: x[0], reverse=True):
            left, right = src[:pos], src[pos:]
            needs_leading_nl = (pos > 0 and src[pos - 1] != "\n")
            prefix_nl = "\n" if needs_leading_nl else ""
            extra_indent = INDENT_UNIT if (pos < len(src) and src[pos] == "}") else ""
            indent_for_insert = indent + extra_indent
            inserted = f"{prefix_nl}{indent_for_insert}{dead_code}\n{indent}"
            src = left + inserted + right

            fn_name = safe_func_name(fn)
            preview = dead_code.strip().replace("\n", " ")[:120]
            print(f"[OBF][{self.name}] file={ctx.project_dir / ctx.file_name} "
                  f"func={fn_name!r} offset={pos} line={line_no} -> insert: {preview}")

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
    ap.add_argument("--file", type=str, default='TheContract.sol', help="指定单个 .sol 文件")
    ap.add_argument("--dir", type=str, default='./project/contracts', help="指定目录（递归处理 .sol)")
    ap.add_argument("--out", type=str, default="./obf_output", help="输出目录")
    ap.add_argument("--enable", type=str, default="cf, dead, literal", help="启用的 Pass 列表（逗号分隔）：cf,dead,layout")
    ap.add_argument("--seed", type=int, default=None)
    
    ap.add_argument("--cf-density", type=float, default=0.5, help="ControlFlow 注入密度（占位）")
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

    base_dir = Path(args.dir) if args.dir else Path(".")
    # 单文件模式
    if args.file:
        src_path = Path(args.file)
        if not src_path.name.endswith(".sol"):
            raise ValueError("指定的文件必须以 .sol 结尾")
        obf_src = run_pipeline_on_file(base_dir, src_path.name, passes)
        out_path = out_dir / src_path.name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(obf_src, encoding="utf-8")
        print(f"[WRITE] {out_path}")
        return

    # 目录模式
    for src_file in enumerate_sol_files(base_dir):
        rel = src_file.relative_to(base_dir)
        obf_src = run_pipeline_on_file(base_dir, src_file.name, passes)
        out_path = out_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(obf_src, encoding="utf-8")
        print(f"[WRITE] {out_path}")

    print("=== Pipeline scaffold complete ===")


if __name__ == "__main__":
    main()