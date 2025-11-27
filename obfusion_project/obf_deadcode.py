import random

from solidity_parser.ast import symtab, solnodes
from typing import List, Any


DEAD_CODE_TEMPLATES = [
    "uint256 uselessVar = 0;",  # Simple unused variable
    "if (1 == 0) { uint256 neverUsed = 42; }",  # Conditional that never executes
    "for (uint256 i = 0; i < 0; i++) { uint256 neverIterated = i; }",  # Unreachable loop
    "require(1 == 0, 'This will never happen');",  # Impossible requirement
    "bytes32 unusedHash = keccak256(abi.encodePacked('dead_code'));",
]

def iter_ast_roots(ast_root) -> List[Any]:
    """把 loaded.ast 规范化为可迭代的根节点列表，过滤 None。"""
    if ast_root is None:
        return []
    if isinstance(ast_root, (list, tuple)):
        return [n for n in ast_root if (n is not None and hasattr(n, "get_all_children"))]
    return [ast_root] if hasattr(ast_root, "get_all_children") else []

def generate_dead_code() -> str:
    return random.choice(DEAD_CODE_TEMPLATES)

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

def collect_top_level_slots(source: str, body_lbrace: int) -> list[tuple[int, str, int]]:
    end = find_block_end(source, body_lbrace)
    if end < 0:
        return []

    slots: list[tuple[int, str, int]] = []

    def _mk_slot(pos: int):
        left = source[:pos]
        line_no = left.count("\n") + 1
        line_start = left.rfind("\n") + 1
        indent = left[line_start: len(left) - len(left[line_start:].lstrip())]
        return (pos, indent, line_no)

    # 1) '{' 后首插槽 —— 跳过空白与注释，并过滤续行   # NEW
    i = _skip_ws_and_comments(source, body_lbrace + 1, end)  # NEW
    if i <= end and not _looks_like_continuation(source, i): # NEW
        slots.append(_mk_slot(i))

    # 2) 扫描顶层分号
    in_line_cmt = in_block_cmt = False
    in_str = False
    str_ch = ""
    escape = False
    depth = 1
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
                # 分号之后：跳过空白+注释，并过滤续行      # NEW
                j = _skip_ws_and_comments(source, i + 1, end)  # NEW
                if j <= end and not _looks_like_continuation(source, j):  # NEW
                    slots.append(_mk_slot(j))
        i += 1

    # 3) '}' 之前（回退空白）——保持不变
    j = end
    while j > body_lbrace and source[j - 1] in " \t\r\n":
        j -= 1
    slots.append(_mk_slot(j))

    # 去重排序
    slots = sorted(set(slots), key=lambda x: x[0])
    return slots

def _skip_ws_and_comments(src: str, i: int, end: int) -> int:
    """向前跳过空白与注释，返回下一个代码字符的位置。"""
    n = len(src)
    while i < end:
        ch = src[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if i + 1 < n and src[i] == "/" and src[i+1] == "/":
            # 行注释
            j = src.find("\n", i + 2)
            if j == -1:
                return end
            i = j + 1
            continue
        if i + 1 < n and src[i] == "/" and src[i+1] == "*":
            # 块注释
            j = src.find("*/", i + 2)
            i = end if j == -1 else j + 2
            continue
        break
    return i

_FORBID_START = set("=><+-*/%&|^!?:.).,]")

def _looks_like_continuation(src: str, pos: int) -> bool:
    """判断 pos 位置是否像是续行操作符开头（不应作为安全语句起始）。"""
    if pos >= len(src):
        return False
    ch = src[pos]
    return ch in _FORBID_START

def safe_func_name(func: solnodes.FunctionDefinition) -> str:
    """更友好的函数名显示。"""
    try:
        n = getattr(func, "name", None)
        if n is None:
            return "<anon>"
        return getattr(n, "value", str(n))
    except Exception:
        return "<anon>"