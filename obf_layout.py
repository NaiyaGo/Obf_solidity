# makes this file easily runnable in Pycharm

from pathlib import Path
from dataclasses import dataclass

from solidity_parser import filesys
from solidity_parser.ast import symtab, solnodes

import json
import subprocess
import os
from typing import Any, Optional, ClassVar, Final
import random
import re
import uuid

# -------------------- parser bridge --------------------

def get_grammar_tree(file_path) -> str:
    # 调用 Node.js 脚本（已支持传入目标文件路径）
    result = subprocess.run(
        ["node", "./getGrammarTree.js", file_path],
        capture_output=True,
        text=True
    )
    if result.returncode != 0 and result.stderr:
        raise RuntimeError(result.stderr)
    return result.stdout

# -------------------- globals from your script --------------------

predefined_keywords = {
    'pragma','solidity','contract','function','public','private','internal',
    'external','pure','view','payable','returns','return','if','else',
    'for','while','do','break','continue','uint','uint256','uint8',
    'int','int256','bool','address','string','bytes','bytes32',
    'true','false','require','assert','revert','emit','event',
    'modifier','constructor','fallback','receive','override','virtual',
    'abstract','interface','library','is','new','delete','this',
    'msg','block','tx','now','revert','selfdestruct','suicide',
    'abi','encodePacked','encode','encodeWithSelector','encodeWithSignature',
    'memory','storage','calldata','indexed','anonymous','constant',
    'immutable','transparent','import','as','from'
}

class Match:
    content = ""  # 运行时用当前源码覆盖

    @classmethod
    def match_concretefunction(cls, funcName):
        pattern = re.compile(rf'\bfunction\s+(?P<name>{re.escape(funcName)})\s*(?=\()', re.ASCII)
        matches = pattern.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])

    @classmethod
    def match_concreteContract(cls, contractName):
        pattern_contract = re.compile(rf'\bcontract\s+(?P<name>{re.escape(contractName)})\s*\b', re.ASCII)
        matches = pattern_contract.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])

    @classmethod
    def match_concreteStruct(cls, structName):
        pattern_struct = re.compile(rf'\bstruct\s+(?P<name>{re.escape(structName)})\s*\b', re.ASCII)
        matches = pattern_struct.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])

    @classmethod
    def match_concreteEnum(cls, enumName):
        pattern_enum = re.compile(rf'\benum\s+(?P<name>{re.escape(enumName)})\s*\b', re.ASCII)
        matches = pattern_enum.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])

    @classmethod
    def match_concreteModifier(cls, modifierName):
        pattern_var = re.compile(rf'\bmodifier\s+(?P<name>{re.escape(modifierName)})\s*(?=\(|\{{)', re.ASCII)
        matches = pattern_var.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])

obfuscatable: set[str] = set()
mapping: dict[str, str] = {}
change_log = []

def collect_definitions(node: Any) -> None:
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type in {"FunctionDefinition","ModifierDefinition","StructDefinition","ContractDefinition","EnumDefinition"} and node.get("name"):
            obfuscatable.add(node["name"])
        elif node_type == "VariableDeclaration" and node.get("name"):
            obfuscatable.add(node["name"])
        for child in node.values():
            collect_definitions(child)
    elif isinstance(node, list):
        for child in node:
            collect_definitions(child)

def rename(name: str) -> str:
    if name not in mapping:
        mapping[name] = f"obf_{uuid.uuid4().hex}"
    return mapping[name]

def add2Log(newName: str, start: int, end: int):
    change_log.append({"newName": newName, "start": start, "end": end})

def _process_member_chain(node: dict[str, Any]) -> int:
    """Rename every segment in a nested MemberAccess chain once."""
    if node.get("type") == "Identifier" and "name" in node:
        start, end = node["range"]
        new_name = rename(node["name"])
        add2Log(new_name, start, end + 1)
        return end + 2  # skip following dot

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
    node_type = node.get("type")

    if node_type == "FunctionDefinition" and node.get("name"):
        old_name = node["name"]
        new_name = rename(old_name)
        start, end = Match.match_concretefunction(old_name)
        add2Log(new_name, start, end)
        return

    if node_type == "ModifierDefinition" and node.get("name"):
        old_name = node["name"]
        new_name = rename(old_name)
        start, end = Match.match_concreteModifier(old_name)
        add2Log(new_name, start, end)
        return

    if node_type == "StructDefinition" and node.get("name"):
        old_name = node["name"]
        new_name = rename(old_name)
        start, end = Match.match_concreteStruct(old_name)
        add2Log(new_name, start, end)
        return

    if node_type == "ContractDefinition" and node.get("name"):
        old_name = node["name"]
        new_name = rename(old_name)
        start, end = Match.match_concreteContract(old_name)
        add2Log(new_name, start, end)
        return

    if node_type == "EnumDefinition" and node.get("name"):
        old_name = node["name"]
        new_name = rename(old_name)
        start, end = Match.match_concreteEnum(old_name)
        add2Log(new_name, start, end)
        return

    if node_type == "UserDefinedTypeName" and node.get("name") and node.get("range"):
        start, end = node["range"]
        new_name = rename(node["name"])
        add2Log(new_name, start, end + 1)
        return

    if node_type == "UserDefinedTypeName" and node.get("namePath") and node.get("range"):
        start, end = node["range"]
        new_name = rename(node["namePath"])
        add2Log(new_name, start, end + 1)
        return

    if node_type == "Identifier" and node.get("name") and node.get("range"):
        start, end = node["range"]
        new_name = rename(node["name"])
        add2Log(new_name, start, end + 1)
        return

def traverse(node, inside_member=False) -> None:
    if inside_member:
        return

    if isinstance(node, dict):
        node_type = node.get("type")

        if node_type == "MemberAccess":
            if not inside_member:
                _process_member_chain(node)
            traverse(node.get("expression"), inside_member=True)
            return

        _handle_named_node(node)

        for child in node.values():
            traverse(child, inside_member=False)
    elif isinstance(node, list):
        for child in node:
            traverse(child, inside_member)

# -------------------- new: entry point for pipeline --------------------

def layout_obfuscate(src: str, file_path: str) -> tuple[str, dict]:
    """
    使用本文件已有函数完成“标识符改名”：
    - 用 getGrammarTree.js 解析 file_path 的 AST（要求 loc/range 打开）
    - 把 src 作为当前源码（用于 Match 的正则定位与最终替换）
    - collect_definitions + traverse 生成 change_log
    - 倒序应用 change_log 到 src，返回新的源码与统计
    """
    global obfuscatable, mapping, change_log
    # 复位全局状态
    try: obfuscatable.clear()
    except Exception: pass
    try: mapping.clear()
    except Exception: pass
    try: change_log.clear()
    except Exception: pass

    # 让正则匹配基于当前源码
    Match.content = src

    # 解析 AST
    ast_json = get_grammar_tree(file_path)
    solidity_ast = json.loads(ast_json)

    # 你的原始流程
    collect_definitions(solidity_ast)
    traverse(solidity_ast)

    # 倒序应用替换
    out_put = src
    for elem in change_log[::-1]:
        out_put = out_put[:elem["start"]] + elem["newName"] + out_put[elem["end"]:]

    stats = {"renamed": len(change_log), "obfuscatable": len(obfuscatable)}
    return out_put, stats

# -------------------- local test only --------------------

if __name__ == '__main__':
    # 单文件测试：把源码与路径都给进去
    test_path = Path("./project/contracts/TestContract.sol")
    text = test_path.read_text(encoding="utf-8")
    new_src, stats = layout_obfuscate(text, str(test_path))
    print("可混淆标识符：", obfuscatable)
    print("stats:", stats)
    print("========obfuscated code========")
    print(new_src)