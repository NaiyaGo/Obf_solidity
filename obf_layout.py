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

def get_grammar_tree() -> str:
    # 调用 Node.js 脚本
    result = subprocess.run(
        ["node", "./getGrammarTree.js"],
        capture_output=True,
        text=True
    )

    return result.stdout



solidity_ast_json_str: str = get_grammar_tree()

# 解析 JSON
solidity_ast: Any = json.loads(solidity_ast_json_str)
#print(json.dumps(solidity_ast, indent=2))


test_path = Path("./project")
test_path = test_path.joinpath("contracts", "TestContract.sol")
with open(test_path, "r", encoding="utf-8", newline='') as f:
    
    text=f.read()
f.close()
#print(text)
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
        'immutable', 'transparent', 'import', 'as', 'from','_'
    }


#单文件需要先找到导入的外来包来确保不混淆其接口调用方法和模块名。

import re







#print("导入的外来包别名和符号：", results)




#print("保护的标识符：", predefined_keywords)



class Match:
    content=text

    @classmethod
    def match_concretefunction(cls,funcName):
        pattern = re.compile(rf'\bfunction\s+(?P<name>{re.escape(funcName)})\s*(?=\()', re.ASCII)
        matches= pattern.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])


    @classmethod
    def match_concreteContract(cls,contractName):
        pattern_contract = re.compile(rf'\bcontract\s+(?P<name>{re.escape(contractName)})\s*\b', re.ASCII)
        matches= pattern_contract.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])


    @classmethod
    def match_concreteStruct(cls,structName):
        pattern_struct = re.compile(rf'\bstruct\s+(?P<name>{re.escape(structName)})\s*\b', re.ASCII)
        matches= pattern_struct.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])


    @classmethod
    def match_concreteEnum(cls,enumName):
        pattern_enum = re.compile(rf'\benum\s+(?P<name>{re.escape(enumName)})\s*\b', re.ASCII)
        matches= pattern_enum.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])

    @classmethod
    def match_concreteModifier(cls,modifierName):
        pattern_var = re.compile(rf'\bmodifier\s+(?P<name>{re.escape(modifierName)})\s*(?=\(|\{{)', re.ASCII)
        matches= pattern_var.search(cls.content)
        return (matches.span("name")[0], matches.span("name")[1])

obfuscatable: set[str] = set()

def collect_definitions(node: Any) -> None:
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type in {"FunctionDefinition", "ModifierDefinition", "StructDefinition",
                         "ContractDefinition", "EnumDefinition"} and node.get("name"):
            obfuscatable.add(node["name"])
        elif node_type == "VariableDeclaration" and node.get("name"):
            obfuscatable.add(node["name"])
        for child in node.values():
            collect_definitions(child)
    elif isinstance(node, list):
        for child in node:
            collect_definitions(child)

import uuid
mapping: dict[str, str] = {}
def rename(name: str) -> str:
    if name not in mapping:
        mapping[name] = f"obf_{uuid.uuid4().hex}"
    return mapping[name]

change_log=[]

'''
declaration range
deinition range{function modifier struct contract enum variable}
usage range

'''


def add2Log(newName:str,start:int,end:int):
    change_log.append({
        "newName":newName,
        "start":start,
        "end":end
    })

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

    if node_type == "Identifier" and node.get("name") and node.get("name") not in predefined_keywords :
        start, end = node["range"]
        new_name = rename(node["name"])
        add2Log(new_name, start, end+1 )
        return
    
    if node_type =="ModifierInvocation" and node.get("name") and node.get("name") not in predefined_keywords:
        old_name = node["name"]
        new_name = rename(old_name)
        start, end = node["range"]
        for i in range(start,end+1):
            if(text[i]=='(' or text[i]==' '):
                end=i
                break
        add2Log(new_name, start, end)
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



collect_definitions(solidity_ast)



traverse(solidity_ast)
'''for elem in change_log:
    print(text[elem["start"]:elem["end"]]+"\t"+str(elem["start"])+"\t"+str(elem["end"]))'''
out_put:str=str(text)
change_log.sort(key=lambda item: item["start"], reverse=True)


for elem in change_log:
        '''        
        print(elem,end="\t")
        print("|"+text[elem["start"]:elem["end"]]+"\t"+str(elem["end"]-elem["start"]))
        
        print(repr("left|"+out_put[elem["start"]-20:elem["start"]]))
        print(repr("middle|"+elem["newName"]))
        print(repr("right|"+out_put[elem["end"]:elem["end"]+20]))
        print(repr("right-1|"+out_put[elem["end"]-1:elem["end"]+19]))
        '''
        out_put=out_put[:elem["start"]]+elem["newName"]+out_put[elem["end"]:]


if __name__ == '__main__':
    #print("可混淆标识符：", obfuscatable)

    print(json.dumps(solidity_ast, indent=2))
    print(text[1674:1692])
    #print("========obfuscated code========")
    print(out_put)