import dataclasses
import random
import warnings
from typing import Optional, Final


@dataclasses.dataclass
class ConfusingMathOperationClass:
    """
    位运算混淆相关方法集合
    """
    pre_defined_bitwise_adder: Final[str] = """
function bitwiseAdd(uint256 _x, uint256 _y) internal pure returns (uint256) {
    // 用位运算模拟加法器
    while (_y != 0) {
        uint256 __carry__ = (_x & _y) << 1;
        _x = _x ^ _y;
        _y = __carry__;
    }
    return _x;
}
"""

    pre_defined_bitwise_subtractor_simpler: Final[str] = """
function bitwiseSubtractByAdd(uint256 _x, uint256 _y) internal pure returns (uint256) {
    // 用位运算模拟减法器
    return bitwiseAdd(_x, bitwiseAdd(~_y, 1));
}
"""

    pre_defined_bitwise_subtractor: Final[str] = """
function bitwiseSubtract(uint256 _x, uint256 _y) internal pure returns (uint256) {
    _x = ~_x;
    // 用位运算模拟加法器
    while (_y != 0) {
        uint256 __carry__ = (_x & _y) << 1;
        _x = _x ^ _y;
        _y = __carry__;
    }
    return _x;
}
"""

    pre_defined_bitwise_multiplier: Final[str] = """
function bitwiseMultiply(uint256 _x, uint256 _y) internal pure returns (uint256) {
    // 用位运算模拟乘法器
    uint256 result = 0;
    while (_y != 0) {
        if ((_y & 1) != 0) {
            result = bitwiseAdd(result, _x);
        }
        _x <<= 1;
        _y >>= 1;
    }
    return result;
}
"""
    pre_defined_bitwise_divider: Final[str] = """
function bitwiseDivide(uint256 _x, uint256 _y) internal pure returns (uint256) {
    require(_y != 0, "Division by zero");
    uint256 quotient = 0;
    uint256 remainder = _x;

    while (remainder >= _y) {
        uint256 tempY = _y;
        uint256 multiple = 1;

        while (bitwiseSubtract(remainder, tempY) >= _y) {
            tempY <<= 1;
            multiple <<= 1;
        }

        remainder = bitwiseSubtract(remainder, tempY);
        quotient = bitwiseAdd(quotient, multiple);
    }

    return quotient;
}
"""
    pre_defined_bitwise_modulo: Final[str] = """
function bitwiseModulo(uint256 _x, uint256 _y) internal pure returns (uint256) {
    require(_y != 0, "Modulo by zero");
    uint256 remainder = _x;

    while (remainder >= _y) {
        remainder = bitwiseSubtract(remainder, _y);
    }

    return remainder;
}
"""
    max_value: Final[int] = 2 ** 16  # 最大支持的数值范围

    # ================ 位运算混淆 ================
    """
    结构（关心）：
      - left
      - operator
      - right
    逻辑：
      - 如果 左手是 数字，或者右手是数字，则可以操作
    最大范围:  2¹⁶
    转换后的结构：
    {
      "type": "FunctionCall",
      "expression": {
        "type": "Identifier",
        "name": "bitwiseAdd"
      },
      "arguments": [
        { ... },   // 原来的 left 节点
        { ... }    // 原来的 right 节点
      ],
      "loc": { ... },
      "range": [ ... ]
    }
    """
    @classmethod
    def transform_add_operation_to_bitwise_adder(
            cls,
            binary_operation_node: dict,
    ) -> dict:
        """
        转换加法操作为位运算加法器调用
         仅处理加法操作
        :param cls: 类对象
        :param binary_operation_node: 二元运算节点
        :return: 新的函数调用节点
        """

        # ------------- 验证输入节点类型 -------------
        if binary_operation_node.get("type") != "BinaryOperation":
            raise TypeError("Input node must be a BinaryOperation")

        left_node: dict = binary_operation_node.get("left")
        right_node: dict = binary_operation_node.get("right")
        operator: str = binary_operation_node.get("operator")

        # 仅处理加法操作
        if operator != "+":
            raise ValueError("Only addition operations are supported")

        # ------------- 提取操作数 -------------
        # 提取左操作数
        if left_node.get("type") == "NumberLiteral":
            left_value: Optional[str] = left_node.get("value")
            if left_value is None:
                left_value = left_node.get("number")
        else:
            raise ValueError("Left operand must be a Literal")

        # 提取右操作数
        if right_node.get("type") == "NumberLiteral":
            right_value: Optional[str] = right_node.get("value")
            if right_value is None:
                right_value = right_node.get("number")
        else:
            raise ValueError("Right operand must be a Literal")

        # ------------- 检查数值范围 -------------
        if left_value is None:
            raise ValueError("Left operand literal value missing")

        if int(left_value) >= cls.max_value:
            warnings.warn(
                f"Left operand value {left_value} exceeds the maximum "
                f"of {cls.max_value}. "
                "Transformation may lead explosion of gas cost."
            )

        if right_value is None:
            raise ValueError("Right operand literal value missing")

        if int(right_value) >= cls.max_value:
            warnings.warn(
                f"Right operand value {right_value} exceeds the maximum "
                f"of {cls.max_value}. "
                "Transformation may lead explosion of gas cost."
            )


        # ============== 构造新的 FunctionCall 节点 ==============
        # 新节点结构：
        #   "type": "FunctionCall",
        #   "expression": {
        #     "type": "Identifier",
        #     "name": "SomeName"
        #   },

        new_obfusion_function_name: str = "NotDefined"
        match operator:
            case "+":
                new_obfusion_function_name = "bitwiseAdd"
            case "-":
                new_obfusion_function_name = random.choice([
                    "bitwiseSubtract",
                    "bitwiseSubtractByAdd"
                ])
            case "*":
                new_obfusion_function_name = "bitwiseMultiply"
            case "/":
                new_obfusion_function_name = "bitwiseDivide"
            case "%":
                new_obfusion_function_name = "bitwiseModulo"
            case _:
                raise ValueError("Unsupported operator for bitwise operation")


        # 添加节点信息
        binary_operation_node.update({
            "type": "FunctionCall",
            "expression": {
                "type": "Identifier",
                "name": new_obfusion_function_name
            }
        })

        # 构造 arguments 列表
        arguments_list: list[dict] = [
            left_node,
            right_node
        ]

        binary_operation_node.update({
            "arguments": arguments_list
        })


        # ============= 删除多余字段 =============
        # 删除 left, right, operator 字段
        binary_operation_node.pop("left", None)
        binary_operation_node.pop("right", None)
        binary_operation_node.pop("operator", None)

        return binary_operation_node


    # ~ and - could do inverse operation
    # Use this idea
    # ~ and - number's sum = even
    @classmethod
    def transform_binary_operation_to_random_other_type(
            cls,
            binary_operation_node: dict,
            contain_unsigned_element: bool = True,
    ) -> dict:
        """
        转换二元运算节点，将 + 变成 - - / - ~ / ~ -，将 - 变成 ~ + / - +
        :param cls: 类对象
        :param binary_operation_node: 二元运算节点
        :param contain_unsigned_element 是否包含无符号元素（无负号，禁止增加 "-"）
        :return: 修改后的二元运算节点
        """
        _acceptable_operation_types: set[str] = {
            "BinaryOperation",  # 二元运算 (+ - * / %)
        }
        # ------------- 验证输入节点类型 -------------
        if binary_operation_node.get("type") not in _acceptable_operation_types:
            raise TypeError("Input node must be a BinaryOperation")


        left_node: dict = binary_operation_node.get("left")
        right_node: dict = binary_operation_node.get("right")
        operator: str = binary_operation_node.get("operator")

        # 只处理 + -
        if operator not in ["+", "-"]:
            raise ValueError("Only addition and subtraction operations are supported")

        # + 变成 - - 或者 - ~ 或者 ~ -
        # - 变成 ~ + 或者 - +
        # 注意前面不可以有+号
        transform_options: list[tuple[str, str] | None]
        if operator == "+":
            transform_options = [
                ("~", "~"),
                None
            ]
            if not contain_unsigned_element:
                transform_options.extend(
                    [
                        ("-", "-"),
                        ("-", "~"),
                        ("~", "-"),
                    ]
                )
            else:
                pass

        else:  # operator == "-"
            transform_options = [
                ("~", "+"),
                None
            ]
            if not contain_unsigned_element:
                transform_options.append(("-", "+"))
            else:
                pass

        chosen_operators = random.choice(transform_options)

        # 包裹左节点和右节点
        if chosen_operators is not None:
            left_operator, right_operator = chosen_operators

            left_node = cls.__wrap_specified_unary(node=left_node, operator=left_operator)
            # note: right side = '+' should change the current operator to '+'
            if right_operator == "+":
                binary_operation_node["operator"] = "+"
            else:
                right_node = cls.__wrap_specified_unary(node=right_node, operator=right_operator)

        binary_operation_node["left"] = left_node
        binary_operation_node["right"] = right_node

        # 返回修改后的节点
        return binary_operation_node

    @classmethod
    def transform_number_literal_to_double_inverse(
            cls,
            literal_node: dict,
            contain_unsigned_element: bool = True,
            max_wrap_times: int = 4
    ) -> dict:
        """
        转换数字字面量节点，添加双重逆运算
        :param cls: 类对象
        :param literal_node: 数字字面量节点
        :param contain_unsigned_element 是否包含无符号元素（无负号，禁止增加 "-"）
        :param max_wrap_times: 最大包装层数
        :return: 修改后的数字字面量节点
        """
        # ------------- 验证输入节点类型 -------------
        if literal_node.get("type") != "NumberLiteral":
            raise TypeError("Input node must be a NumberLiteral")

        literal_node: dict = cls.wrap_mix_random_xor_and_unary(
            node = literal_node,
            contain_unsigned_element = contain_unsigned_element,
            max_random_number = 255,
            max_wrap_times = max_wrap_times
        )

        return literal_node

    @classmethod
    def transform_unary_operation_to_double_inverse(
            cls,
            unary_operation_node: dict,
            contain_unsigned_element = True,
            max_wrap_times: int = 4
    ) -> dict:
        """
        转换一元运算节点，添加双重逆运算
        :param cls: 类对象
        :param unary_operation_node: 一元运算节点
        :param contain_unsigned_element 是否包含无符号元素（无负号，禁止增加 "-"）
        :param max_wrap_times: 最大包装层数
        :return: 修改后的一元运算节点
        """
        # ------------- 验证输入节点类型 -------------
        if unary_operation_node.get("type") != "UnaryOperation":
            raise TypeError("Input node must be a UnaryOperation")

        sub_expression_node: dict = unary_operation_node.get("subExpression")

        # 所有一元运算符都可以处理
        unary_operation_node: dict = cls.wrap_mix_random_xor_and_unary(
            node = sub_expression_node,
            contain_unsigned_element = contain_unsigned_element,
            max_random_number = 255,
            max_wrap_times = max_wrap_times
        )

        return unary_operation_node

    @classmethod
    def transform_binary_operation_operand_to_double_inverse(
            cls,
            binary_operation_node: dict,
            operand: str,
            contain_unsigned_element: bool = True,
            max_wrap_times: int = 4
    ) -> dict:
        """
        转换二元运算节点的指定操作数，添加双重逆运算
        :param cls: 类对象
        :param binary_operation_node: 二元运算节点
        :param contain_unsigned_element 是否包含无符号元素（无负号，禁止增加 "-"）
        :param operand: 指定操作数 (+ - * / %)
        :param max_wrap_times: 最大包装层数
        :return:
        """
        # ------------- 验证输入节点类型 -------------
        if binary_operation_node.get("type") != "BinaryOperation":
            raise TypeError("Input node must be a BinaryOperation")

        return cls.wrap_mix_random_xor_and_unary(
            node = binary_operation_node.get(operand),
            contain_unsigned_element = contain_unsigned_element,
            max_random_number = 255,
            max_wrap_times = max_wrap_times
        )

    @classmethod
    def transform_index_access_to_double_inverse(
            cls,
            index_access_node: dict,
            contain_unsigned_element: bool = True,
            max_wrap_times: int = 4
    ) -> dict:
        """
        转换索引访问节点的索引表达式，添加双重逆运算
        :param cls: 类对象
        :param index_access_node: 索引访问节点
        :param contain_unsigned_element 是否包含无符号元素（无负号，禁止增加 "-"）
        :param max_wrap_times: 最大包装层数
        :return: 修改后的索引访问节点
        """
        # ------------- 验证输入节点类型 -------------
        if index_access_node.get("type") != "IndexAccess":
            raise TypeError("Input node must be an IndexAccess")

        index_node: dict = index_access_node.get("index")
        index_access_node["index"] = cls.wrap_mix_random_xor_and_unary(
            node = index_node,
            contain_unsigned_element = contain_unsigned_element,
            max_random_number = 255,
            max_wrap_times = max_wrap_times
        )

        return index_access_node


    @staticmethod
    def __wrap_specified_unary(
            node: dict,
            operator: str
    ) -> dict:
        """
        包裹指定的一元运算符
         仅支持 ~ 和 -
        :param node: 只能是 Literal 或者 Identifier
        :param operator: 指定的一元运算符 ('~' 或者 '-')
        :return: 新的 UnaryOperation 节点
        """

        # node should be "Literal"  # 常量值 (数字, 字符串)
        # Or Identifier (but on the right hand side of the expression)
        # Assignment right hand side
        if node.get("type") not in (
                "Literal",
                "Identifier"
        ):
            raise TypeError("Node must be a Literal or Identifier")

        # check operator validity
        if operator not in ["~", "-"]:
            raise ValueError("Operator must be '~' or '-'")


        # 用括号包裹这一层
        node = {
            "type": "ParenthesizedExpression",
            "expression": node
        }

        # 再做符号运算
        node = {
            "type": "UnaryOperation",
            "operator": operator,
            "subExpression": node,
            "prefix": True
        }

        return node

    @staticmethod
    def __wrap_random_any_unary(
            node: dict,
            contain_unsigned_element: bool = True,
            depth: int = 1
    ) -> dict:
        """
        随机包裹任意一元运算符
         支持 ~ 和 -
        递归包装 depth 次
        :param node: 只能是 Literal 或者 Identifier
        :param depth: 包装深度
        :return: 新的 UnaryOperation 节点
        """
        ops = ["~"]
        if not contain_unsigned_element:
            ops.append("-")
        else:
            pass

        # randomly wrap unary operations for depth times
        for _ in range(depth):
            operator = random.choice(ops)
            ConfusingMathOperationClass.__wrap_specified_unary(node=node, operator=operator)

        return node

    @classmethod
    def __wrap_random_unary(cls,
                            node: dict,
                            contain_unsigned_element: bool = True,
                            max_wrap_times: int = 3
                            ) -> dict:
        """
        随机包裹任意一元运算符
         支持 ~ 和 -
         包装随机偶数层
        :param node: 只能是 Literal 或者 Identifier
        :param max_wrap_times: 最大包装层数
        :return: 新的 UnaryOperation 节点
        """
        depth: int = random.randint(1, max_wrap_times) * 2 # 保证是偶数层

        return cls.__wrap_random_any_unary(node,
                                           contain_unsigned_element,
                                           depth)



    @staticmethod
    def __wrap_xor(node: dict,
                   max_random_number: int = 255
                   ) -> dict:
        """
        包裹异或运算 2 次
        以实现数值不变的混淆效果
        例如:  x  ->  ((x ^ r) ^ r)
        其中 r 是随机数
        :param node: 只能是 NumberLiteral
        :param max_random_number: 随机数最大值
        :return: 新的 BinaryOperation 节点
        """
        # node should be "NumberLiteral"  # 常量值 (数字)
        if node.get("type") not in (
                "NumberLiteral"
        ):
            raise TypeError("Node must be a Literal or NumberLiteral")

        random_number: int = random.randint(0, max_random_number)

        # 再做异或运算 2 次
        for _ in range(2):
            # 用括号包裹这一层
            node: dict = {
                "type": "ParenthesizedExpression",
                "expression": node
            }

            node: dict = {
                "type": "BinaryOperation",
                "operator": "^",
                "left": node,
                "right": {
                    "type": "NumberLiteral",
                    "number": str(random_number),
                    # 字面量 wei ether gwei
                    "subdenomination": None  # Solidity AST 规范要求
                }
            }

        # 返回最终节点
        return node


    @classmethod
    def __wrap_random_xor(cls, node,
                          max_random_number: int,
                          max_wrap_times: int = 3) -> dict:
        """
        随机包裹异或运算 多次
         以实现数值不变的混淆效果
        例如:  x  ->  (((x ^ r1) ^ r1) ^ r2) ^ r2)
        其中 r1, r2 是随机数
        这里包装的次数是随机的，最多 max_wrap_times 次
        例如 max_wrap_times = 3，可能包装 0~3 次
        :param node: 只能是 NumberLiteral
        :param max_random_number: 随机数最大值
        :param max_wrap_times: 最大包装层数
        :return:
        """
        wrap_number: int = random.randint(0, max_wrap_times)
        for _ in range(wrap_number):
            node = cls.__wrap_xor(node=node, max_random_number=max_random_number)

        return node


    @classmethod
    def wrap_mix_random_xor_and_unary(
            cls,
            node: dict,
            contain_unsigned_element = True,
            max_random_number: int = 255,
            max_wrap_times: int = 3
    ) -> dict:
        """
        混合随机包裹异或运算和一元运算 多次
         以实现数值不变的混淆效果
        例如:  x  ->  (((((x ^ r1) ^ r1) - ) ~ ) ^ r2) ^ r2)
        其中 r1, r2 是随机数
        这里包装的次数是随机的，最多 max_wrap_times 次
        例如 max_wrap_times = 3，可能包装 0~3 次
        先随机选择包装次数，然后每次随机选择包装 xor 还是 unary
        :param node:  只能是 NumberLiteral
        :param contain_unsigned_element 是否包含无符号元素（无负号，禁止增加 "-"）
        :param max_random_number:  随机数最大值
        :param max_wrap_times: 最大包装层数
        :return: 新的节点
        """
        wrap_times: int = random.randint(0, max_wrap_times)
        any_node: dict = node
        # Random choose to wrap xor or unary
        for _ in range(wrap_times):
            wrap_choice: str = random.choice(["xor", "unary"])
            if wrap_choice == "xor":
                any_node = cls.__wrap_xor(node=any_node, max_random_number=max_random_number)
            else:  # wrap_choice == "unary"
                any_node = cls.__wrap_random_unary(
                    node=any_node,
                    contain_unsigned_element=contain_unsigned_element,
                    max_wrap_times=1
                )


        return any_node

    @classmethod
    def collect_identifiers(cls,
                            node: dict) -> list[str]:
        """
        递归收集节点里的所有 Identifier 名字
        :param node: AST 节点
        :return: Identifier 对象列表
        """
        ids = []
        if isinstance(node, dict):
            if node.get("type") == "Identifier":
                ids.append(node.get("name"))
            for v in node.values():
                ids.extend(cls.collect_identifiers(v))
        elif isinstance(node, list):
            for item in node:
                ids.extend(cls.collect_identifiers(item))
        return ids

    @classmethod
    def wrap_node_as_private_function(
            cls,
            node: dict,
            func_counter: int = 0
    ) -> tuple[dict, dict]:
        """
        把当前节点封装成私有函数，并返回 (函数定义, 调用节点)

        :param cls: 类对象
        :param node: AST 节点
        :param func_counter: 用于生成唯一函数名的计数器
        :return: (函数定义节点, 调用节点)
        """
        func_name = f"__obf_func_{func_counter}_{random.randint(1000, 9999)}"
        identifiers = list(set(cls.collect_identifiers(node)))  # 去重

        # 构造参数列表
        # 暴力丢进去所有的函数参数
        parameters = [{"type": "VariableDeclaration", "name": ident, "datatype": "uint256"} for ident in identifiers]

        # 构造函数定义
        func_def = {
            "type": "FunctionDefinition",
            "name": func_name,
            "visibility": "internal",
            "stateMutability": "pure",
            "parameters": parameters,
            "returnParameters": [{"type": "ElementaryTypeName", "name": "uint256"}],
            "body": {
                "type": "Block",
                "statements": [{
                    "type": "ReturnStatement",
                    "expression": node
                }]
            }
        }

        # 构造调用节点
        call_node = {
            "type": "FunctionCall",
            "expression": {"type": "Identifier", "name": func_name},
            "arguments": [{"type": "Identifier", "name": ident} for ident in identifiers]
        }

        return func_def, call_node

