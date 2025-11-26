import pprint

import json
import subprocess
from typing import Any, Optional


def get_grammar_tree_js(path: str = r"./getGrammarTree.js") -> str:
    """
    获取 Solidity 代码的语法树 JSON 字符串
    通过调用 Node.js 脚本实现
    例如:
    {
      "type": "SourceUnit",
      "children": [
        ...
      ]
    }
    该 JSON 字符串可以通过 json.loads() 解析为 Python 对象
    例如:
    solidity_ast = json.loads(solidity_ast_json_str)
    这样就得到了 Solidity 代码的 AST，可以进行后续处理
    例如用于代码混淆等操作
    该函数依赖于 Node.js 环境和 npm install @solidity-parser/parser 安装的包
    需要确保 Node.js 已安装且可用
    :param path: Node.js 脚本路径
    :return: Solidity 代码的语法树 JSON 字符串
    """
    # 调用 Node.js 脚本
    result = subprocess.run(
        ["node", path],
        capture_output=True,
        text=True
    )

    return result.stdout


def find_all_given_operations(
        node: dict | list,
        expression_types_given: set[str],
        expressions_list: Optional[list] = None
) -> list[dict]:
    """
    递归查找 AST 中所有指定类型的表达式节点
    return: 包含所有找到的指定类型表达式节点的列表
    例如 expression_types_given = { "BinaryOperation", "UnaryOperation" }
    则会找到所有二元运算和一元运算节点
    递归遍历 AST 节点，如果节点类型在 expression_types_given 中，则添加到 expressions_list 中
    然后继续递归遍历子节点
    直到遍历完整个 AST
    这样可以收集所有指定类型的表达式节点
    例如用于收集所有数学表达式节点
    以便后续进行混淆处理
    :param node: 当前 AST 节点
    :param expression_types_given: 需要查找的表达式类型集合
    :param expressions_list: 用于存储找到的表达式节点的列表
    :return: 包含所有找到的指定类型表达式节点的列表
    """

    # Type Guard for expressions_list
    if not isinstance(expression_types_given, set):
        raise TypeError("expression_types must be a set")

    if expressions_list is None:
        expressions_list = []
    elif not isinstance(expressions_list, list):
        raise TypeError("expressions_list must be a list or None")
    else:
        pass

    # ------------------- 递归筛选 -------------------
    if isinstance(node, dict):
        if node.get("type") in expression_types_given:
            expressions_list.append(node)

        # 遍历子节点
        for child in node.values():
            find_all_given_operations(
                node=child,
                expression_types_given=expression_types_given,
                expressions_list=expressions_list
            )
    elif isinstance(node, list):
        for item in node:
            find_all_given_operations(
                item,
                expression_types_given=expression_types_given,
                expressions_list=expressions_list
            )
    else:
        pass

    return expressions_list


if __name__ == '__main__':

    solidity_ast_json_str: str = get_grammar_tree_js()

    # 解析 JSON
    solidity_ast: Any = json.loads(solidity_ast_json_str)

    # 用于引用储存所有数学表达式节点
    all_math_operations: list = []

    # 定义需要收集的表达式类型
    expression_types: set[str] = {
        "BinaryOperation",  # 二元运算 (+ - * / %)
        "UnaryOperation",  # 一元运算 (++ -- -x)
        # "FunctionCall",  # 函数调用
        # "MemberAccess",      # msg.sender / obj.prop
        "IndexAccess",  # arr[i]
        # "Identifier",        # 变量名
        "Literal"  # 常量值 (数字, 字符串)
    }

    """
    递归遍历 AST，查找所有数学表达式节点
    将找到的节点添加到 expressions_list 中
    注意是返回引用，不是拷贝
    @param node: 当前 AST 节点
    @param expressions_list: 用于存储找到的表达式节点的列表
    @return: 包含所有找到的数学表达式节点的列表
    """


    # 调用函数查找所有数学表达式节点
    found_expressions: list[dict] = find_all_given_operations(
        node=solidity_ast,
        expression_types_given=expression_types
    )
    for expr in found_expressions:
        pprint.pprint(expr.items())