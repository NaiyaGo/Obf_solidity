# layout_obfuscate_runtime.py
# 无硬编码版本：通过 get_grammar_tree(file_path) 解析 AST，
# 用传入的 src 做正则定位与文本替换；返回 (new_src, stats)

import subprocess
import json
import re
import uuid

from typing import Any
from pathlib import Path

# -------------------- JS 桥接 --------------------
def get_grammar_tree(file_path: str) -> str:
    """调用 Node 侧 getGrammarTree.js(需支持 argv[2] 指定文件路径）。"""
    res = subprocess.run(
        ["node", "./obfusion_project/getGrammarTree.js", file_path],
        capture_output=True,
        text=True
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr or "getGrammarTree.js failed")
    return res.stdout

# -------------------- 你原脚本里的全局对象（保留） --------------------
predefined_keywords = {
    'pragma', 'solidity', 'contract', 'function', 'public', 'private', 'internal',
    'external', 'pure', 'view', 'payable', 'returns', 'return', 'if', 'else',
    'for', 'while', 'do', 'break', 'continue', 'uint', 'uint256', 'uint8',
    'int', 'int256', 'bool', 'address', 'string', 'bytes', 'bytes32',
    'true', 'false', 'require', 'assert', 'revert', 'emit', 'event',
    'modifier', 'constructor', 'fallback', 'receive', 'override', 'virtual',
    'abstract', 'interface', 'library', 'is', 'new', 'delete', 'this',
    'msg', 'block', 'tx', 'now', 'revert', 'selfdestruct', 'suicide',
    'abi', 'encodePacked', 'encode', 'encodeWithSelector', 'encodeWithSignature',
    'memory', 'storage', 'calldata', 'indexed', 'anonymous', 'constant',
    'immutable', 'transparent', 'import', 'as', 'from', '_', 'push'
}

class Match:
    # 注意：运行时会把 content 设置为当前 src
    content: str = ""

    @classmethod
    def match_concretefunction(cls, funcName):
        pattern = re.compile(rf'\bfunction\s+(?P<name>{re.escape(funcName)})\s*(?=\()', re.ASCII)
        m = pattern.search(cls.content)
        return (m.span("name")[0], m.span("name")[1])

    @classmethod
    def match_concreteContract(cls, contractName):
        pattern = re.compile(rf'\bcontract\s+(?P<name>{re.escape(contractName)})\s*\b', re.ASCII)
        m = pattern.search(cls.content)
        return (m.span("name")[0], m.span("name")[1])

    @classmethod
    def match_concreteStruct(cls, structName):
        pattern = re.compile(rf'\bstruct\s+(?P<name>{re.escape(structName)})\s*\b', re.ASCII)
        m = pattern.search(cls.content)
        return (m.span("name")[0], m.span("name")[1])

    @classmethod
    def match_concreteEnum(cls, enumName):
        pattern = re.compile(rf'\benum\s+(?P<name>{re.escape(enumName)})\s*\b', re.ASCII)
        m = pattern.search(cls.content)
        return (m.span("name")[0], m.span("name")[1])

    @classmethod
    def match_concreteModifier(cls, modifierName):
        pattern = re.compile(rf'\bmodifier\s+(?P<name>{re.escape(modifierName)})\s*(?=\(|\{{)', re.ASCII)
        m = pattern.search(cls.content)
        return (m.span("name")[0], m.span("name")[1])

# 这些集合在每次调用入口时会被重置
obfuscatable: set[str] = set()
mapping: dict[str, str] = {}
change_log: list[dict] = []

def collect_definitions(node: Any) -> None:
    if isinstance(node, dict):
        t = node.get("type")
        if t in {"FunctionDefinition", "ModifierDefinition", "StructDefinition",
                 "ContractDefinition", "EnumDefinition"} and node.get("name"):
            obfuscatable.add(node["name"])
        elif t == "VariableDeclaration" and node.get("name"):
            obfuscatable.add(node["name"])
        for v in node.values():
            collect_definitions(v)
    elif isinstance(node, list):
        for v in node:
            collect_definitions(v)

def rename(name: str) -> str:
    if name not in mapping:
        mapping[name] = f"obf_{uuid.uuid4().hex}"
    return mapping[name]

def add2Log(newName: str, start: int, end: int):
    change_log.append({"newName": newName, "start": start, "end": end})

def _process_member_chain(node: dict[str, Any]) -> int:
    # 重命名链式 MemberAccess，每个段只处理一次
    if node.get("type") == "Identifier" and "name" in node and node["name"] not in predefined_keywords:
        start, end = node["range"]
        new_name = rename(node["name"])
        add2Log(new_name, start, end + 1)
        return end + 2

    expression = node.get("expression")
    if isinstance(expression, dict):
        current_start = _process_member_chain(expression)
    else:
        current_start = node.get("range", [0, 0])[0]

    chain_end = node.get("range", [0, 0])[1]
    member_name = node.get("memberName")
    if member_name:
        new_name = rename(member_name)
        add2Log(new_name, current_start, chain_end + 1)
    return chain_end + 2

def _handle_named_node(node: dict[str, Any]) -> None:
    t = node.get("type")

    if t == "FunctionDefinition" and node.get("name") and node.get("name") not in predefined_keywords:
        old = node["name"]
        new = rename(old)
        s, e = Match.match_concretefunction(old)
        add2Log(new, s, e); return

    if t == "ModifierDefinition" and node.get("name") and node.get("name") not in predefined_keywords:
        old = node["name"]
        new = rename(old)
        s, e = Match.match_concreteModifier(old)
        add2Log(new, s, e); return

    if t == "StructDefinition" and node.get("name") and node.get("name") not in predefined_keywords:
        old = node["name"]
        new = rename(old)
        s, e = Match.match_concreteStruct(old)
        add2Log(new, s, e); return

    if t == "ContractDefinition" and node.get("name") and node.get("name") not in predefined_keywords:
        old = node["name"]
        new = rename(old)
        s, e = Match.match_concreteContract(old)
        add2Log(new, s, e); return

    if t == "EnumDefinition" and node.get("name") and node.get("name") not in predefined_keywords:
        old = node["name"]
        new = rename(old)
        s, e = Match.match_concreteEnum(old)
        add2Log(new, s, e); return

    if t == "UserDefinedTypeName" and node.get("name") and node.get("range") and node.get("name") not in predefined_keywords:
        s, e = node["range"]
        new = rename(node["name"])
        add2Log(new, s, e + 1); return

    if t == "UserDefinedTypeName" and node.get("namePath") and node.get("range") and node.get("namePath") not in predefined_keywords:
        s, e = node["range"]
        new = rename(node["namePath"])
        add2Log(new, s, e + 1); return

    if t == "Identifier" and node.get("name") and node.get("name") not in predefined_keywords:
        s, e = node["range"]
        new = rename(node["name"])
        add2Log(new, s, e + 1); return

    if t == "ModifierInvocation" and node.get("name") and node.get("name") not in predefined_keywords:
        old = node["name"]
        new = rename(old)
        s, e = node["range"]
        # 截到 '(' 或空格为止
        for i in range(s, e + 1):
            if (Match.content[i] == '(') or (Match.content[i] == ' '):
                e = i
                break
        add2Log(new, s, e); return

def traverse(node: Any, inside_member: bool = False) -> None:
    if inside_member:
        return
    if isinstance(node, dict):
        t = node.get("type")
        if t == "MemberAccess":
            if not inside_member:
                _process_member_chain(node)
            traverse(node.get("expression"), inside_member=True)
            return
        _handle_named_node(node)
        for v in node.values():
            traverse(v, inside_member=False)
    elif isinstance(node, list):
        for v in node:
            traverse(v, inside_member)

def _apply_changes(src: str) -> str:
    """把 change_log 按 start 逆序应用到 src。"""
    out = src
    change_log.sort(key=lambda item: item["start"], reverse=True)
    for c in change_log:
        out = out[:c["start"]] + c["newName"] + out[c["end"]:]
    return out

# -------------------- 入口：无硬编码版本 --------------------
def layout_obfuscate(src: str, file_path: str) -> tuple[str, dict]:
    """
    - src: 当前要混淆的源码（字符串）
    - file_path: 让 Node 解析的“同一份源”的磁盘路径（由外部保证 file_path 内容与 src 一致）
      * 若你在 pipeline 里已经把 src 写到了一个临时路径 tmp.sol, 则把 tmp.sol 的绝对路径传进来即可
    """
    # 1) 重置全局状态
    obfuscatable.clear()
    mapping.clear()
    change_log.clear()
    Match.content = src  # 供正则定位

    # 2) 解析 AST(JSON)
    ast_json = get_grammar_tree(file_path)
    solidity_ast = json.loads(ast_json)

    # 3) 收集与遍历（与你原脚本一致）
    collect_definitions(solidity_ast)
    traverse(solidity_ast)

    # 4) 应用替换
    new_src = _apply_changes(src)
    stats = {
        "changed": new_src != src,
        "renamed": len(change_log),
        "obfuscatable": len(obfuscatable),
    }
    return new_src, stats

# -------------------- 可选：本地测试 CLI --------------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Layout obfuscation (no hardcode)")
    ap.add_argument("--file", required=True, help="要混淆的 .sol 文件路径（将传给 getGrammarTree.js）")
    args = ap.parse_args()

    p = Path(args.file)
    src_text = p.read_text(encoding="utf-8")
    out_text, info = layout_obfuscate(src_text, str(p))
    print("stats:", info)
    print("========obfuscated code========")
    print(out_text)