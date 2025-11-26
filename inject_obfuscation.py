from pathlib import Path
from dataclasses import dataclass
import random
import os
import shutil
import argparse

from solidity_parser import filesys
from solidity_parser.ast import symtab, solnodes

# 死代码模板
DEAD_CODE_TEMPLATES = [
    "uint256 uselessVar = 0;",  # Simple unused variable
    "if (1 == 0) { uint256 neverUsed = 42; }",  # Conditional that never executes
    "for (uint256 i = 0; i < 0; i++) { uint256 neverIterated = i; }",  # Unreachable loop
    "require(1 == 0, 'This will never happen');",  # Impossible requirement
    "bytes32 unusedHash = keccak256(abi.encodePacked('dead_code'));",
]

@dataclass
class Insertion:
    func: solnodes.FunctionDefinition
    dead_code: str

def generate_dead_code() -> str:
    return random.choice(DEAD_CODE_TEMPLATES)

def _safe_func_name(func: solnodes.FunctionDefinition) -> str:
    # name 可能是 Ident 或 SpecialFunctionKind；尽量给出可读名称
    try:
        n = getattr(func, "name", None)
        if n is None:
            return "<anon>"
        # Ident 通常有 .value；退化到 str(n)
        return getattr(n, "value", str(n))
    except Exception:
        return "<anon>"

def find_body_insert_offset(source: str, func: solnodes.FunctionDefinition) -> int:
    """
    以函数体 Block 的 '{' 为锚点，返回 '{' 之后第一个非空白字符的偏移。
    若缺少 code（如 interface/abstract），返回 -1 表示不插入。
    """
    code_block = getattr(func, "code", None)
    if code_block is None:
        return -1
    try:
        i = code_block.start_buffer_index  # '{' 的位置
    except Exception:
        return -1

    # i 指向 '{'，向后移动一位，然后跳过空白/换行
    i += 1
    while i < len(source) and source[i] in " \t\r\n":
        i += 1
    return i if i < len(source) else -1

def _find_block_end(source: str, open_brace_idx: int) -> int:
    """
    给定函数体 '{' 的位置，返回与之匹配的 '}' 的位置。
    识别 // 行注释、/* */ 块注释、'...'/"..." 字符串与转义，避免误判。
    找不到时返回 -1。
    """
    i = open_brace_idx + 1
    n = len(source)
    depth = 1
    in_line_cmt = False
    in_block_cmt = False
    in_str = False
    str_ch = ""
    escape = False
    paren = 0  # 仅用于跳过括号内的内容（这里不参与深度）

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
            # 不在注释/字符串
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
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1

def _collect_top_level_slots(source: str, body_lbrace: int) -> list[tuple[int, str, int]]:
    """
    从函数体 '{' 起，收集“顶层安全插入点”：
    - '{' 之后的首个位置
    - 顶层分号 ';'（brace 深度==1 && paren/bracket 深度==0 && 不在注释/字符串）之后
    - 匹配的 '}' 之前
    返回: 列表[(insert_pos, indent, line_no)]
    """
    end = _find_block_end(source, body_lbrace)
    if end < 0:
        return []

    slots: list[tuple[int, str, int]] = []

    def _mk_slot(pos: int):
        left = source[:pos]
        line_no = left.count("\n") + 1
        line_start = left.rfind("\n") + 1
        indent = left[line_start: len(left) - len(left[line_start:].lstrip())]
        return (pos, indent, line_no)

    # 1) '{' 后首插槽（跳过空白）
    i = body_lbrace + 1
    while i < end and source[i] in " \t\r\n":
        i += 1
    slots.append(_mk_slot(i))

    # 2) 扫描顶层分号
    in_line_cmt = in_block_cmt = False
    in_str = False
    str_ch = ""
    escape = False
    depth = 1          # 从函数体开始
    paren = 0
    bracket = 0

    i = body_lbrace + 1
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
                # 分号之后跳过空白，记录插槽
                j = i + 1
                while j < end and source[j] in " \t\r\n":
                    j += 1
                slots.append(_mk_slot(j))
        i += 1

    # 3) '}' 之前（回退空白）
    j = end
    while j > body_lbrace and source[j - 1] in " \t\r\n":
        j -= 1
    slots.append(_mk_slot(j))

    # 去重并按位置排序（可选）
    slots = sorted(set(slots), key=lambda x: x[0])
    return slots

def _iter_ast_roots(ast_root):
    """
    将 loaded_src.ast 规范化为可迭代的根节点序列，自动过滤 None 和没有 get_all_children 的对象。
    兼容: 单个根、列表/元组根、可能夹杂 None 的情况。
    """
    if ast_root is None:
        return []
    if isinstance(ast_root, (list, tuple)):
        return [n for n in ast_root if (n is not None and hasattr(n, "get_all_children"))]
    return [ast_root] if hasattr(ast_root, "get_all_children") else []

def apply_insertions(source: str, insertions: list[Insertion], file_label: str) -> str:
    """
    为每个目标函数随机选择一个“顶层安全插槽”，逆序写入。
    插入时若当前位置非行首，会先换行再写入。
    若插在 '}' 前，会在当前缩进基础上额外加一层缩进（4 空格）以保持块内对齐。
    """
    if not insertions:
        print(f"[INFO] {file_label}: 无可插入的目标函数")
        return source

    prepared = []
    for ins in insertions:
        code_block = getattr(ins.func, "code", None)
        if code_block is None:
            continue
        try:
            lbrace = code_block.start_buffer_index
        except Exception:
            continue

        slots = _collect_top_level_slots(source, lbrace)
        if not slots:
            continue

        # 随机选择一个插槽
        pos, indent, line_no = random.choice(slots)
        prepared.append((pos, indent, line_no, ins))

    if not prepared:
        print(f"[INFO] {file_label}: 未找到可用插槽（函数可能为空体或解析失败）")
        return source

    INDENT_UNIT = "    "  # 统一 4 空格缩进

    # 逆序写入，避免偏移串扰
    for pos, indent, line_no, ins in sorted(prepared, key=lambda x: x[0], reverse=True):
        left, right = source[:pos], source[pos:]

        # 1) 若不在行首，先换行
        needs_leading_nl = (pos > 0 and source[pos - 1] != "\n")
        prefix_nl = "\n" if needs_leading_nl else ""

        # 2) 若正好插在 '}' 之前，则在当前缩进上额外加一层缩进，保证仍在块内对齐
        extra_indent = INDENT_UNIT if (pos < len(source) and source[pos] == "}") else ""
        indent_for_insert = indent + extra_indent

        # 3) 组装插入文本：前置换行(如需) + 缩进 + 代码 + 换行 + 原缩进（保留后续行缩进）
        dead_line = f"{prefix_nl}{indent_for_insert}{ins.dead_code}\n{indent}"

        source = left + dead_line + right

        func_name = _safe_func_name(ins.func)
        preview = ins.dead_code.strip().replace("\n", " ")[:120]
        print(f"[OBF] file={file_label} func={func_name!r} offset={pos} line={line_no} -> insert: {preview}")

    return source

def insert_dead_code_into_functions(project_dir: Path, file_name: str, density: float = 0.3) -> str:
    """
    在指定文件的若干函数中注入死代码；返回修改后的源码字符串。
    """
    # VFS + 符号表
    vfs = filesys.VirtualFileSystem(project_dir, None, [])
    builder = symtab.Builder2(vfs)
    builder.process_or_find_from_base_dir(file_name)

    loaded = vfs.sources[file_name]
    ast1_root = loaded.ast
    src_code = loaded.contents

    insertions: list[Insertion] = []
    selected, total_funcs = 0, 0

    # 关键：安全地迭代根节点，过滤 None
    for node in _iter_ast_roots(ast1_root):
        # get_all_children 过滤 FunctionDefinition
        for func in node.get_all_children(lambda x: isinstance(x, solnodes.FunctionDefinition)):
            total_funcs += 1
            # 仅对有函数体（code）的函数插入（interface/abstract 会没有 code）
            if getattr(func, "code", None) is None:
                continue
            if random.random() < density:
                dc = generate_dead_code()
                insertions.append(Insertion(func=func, dead_code=dc))
                selected += 1

    print(f"[SCAN] {project_dir / file_name}: 共发现函数 {total_funcs} 个；将对 {selected} 个函数尝试注入。")
    modified_code = apply_insertions(src_code, insertions, file_label=str(project_dir / file_name))
    return modified_code

def main():
    ap = argparse.ArgumentParser(description="Solidity Dead-Code Injector (prints per-change logs)")
    ap.add_argument("--file", type=str, default="./example/gptcomments/TheContract.sol", help="指定一个 .sol 文件")
    ap.add_argument("--dir", type=str, default=None, help="指定目录递归处理 .sol 文件")
    ap.add_argument("--out", type=str, default="./output", help="输出目录")
    ap.add_argument("--density", type=float, default=0.9, help="插入密度 (0.0-1.0)")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（可复现实验）")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if not args.file and not args.dir:
        raise ValueError("必须指定 --file 或 --dir")

    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        src_path = Path(args.file)
        if not src_path.name.endswith(".sol"):
            raise ValueError("指定的文件必须以 .sol 结尾")
        result = insert_dead_code_into_functions(Path(src_path.parent), src_path.name, density=args.density)
        out_path = out_dir / src_path.name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result, encoding="utf-8")
        print(f"[DONE] 单文件写入完成 → {out_path}")
        return

    # 目录模式
    for root, _, files in os.walk(args.dir):
        for f in files:
            if f.endswith(".sol"):
                rel_dir = Path(root).relative_to(Path(args.dir))
                rel_file = str(rel_dir / f) if str(rel_dir) != "." else f
                result = insert_dead_code_into_functions(Path(args.dir), rel_file, density=args.density)
                out_path = out_dir / rel_dir / f
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(result, encoding="utf-8")
                print(f"[DONE] 文件写入完成 → {out_path}")

    print("=== 全目录混淆完成 ===")

if __name__ == "__main__":
    main()