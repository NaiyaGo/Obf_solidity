if __name__ == '__main__':
    pass

from pathlib import Path
from dataclasses import dataclass
import random
from typing import List

from solidity_parser import filesys
from solidity_parser.ast import symtab, solnodes

files_to_obfuscate = ['TheContract.sol']
project_dir = Path('./gptcomments')

vfs = filesys.VirtualFileSystem(project_dir, None, [])
sym_builder = symtab.Builder2(vfs)


def should_obfuscate_literal(literal):
    return isinstance(literal.value, str) and len(literal.value) > 1


@dataclass
class Obfuscation:
    original_literal: solnodes.Literal
    obfuscated_expr: solnodes.Expr
    start_index: int
    end_index: int


def obfuscate_string_literal(literal):
    original_string = literal.value
    chars = list(original_string)
    return _create_manual_concat_method(chars, original_string)


def _create_manual_concat_method(chars, original_string):
    if len(chars) == 0:
        return solnodes.Literal("")

    char_literals = [solnodes.Literal(char) for char in chars]

    result = char_literals[0]

    for i in range(1, len(char_literals)):
        result = solnodes.BinaryOp(
            left=result,
            right=char_literals[i],
            op=solnodes.BinaryOpCode.ADD
        )

    return result


def find_string_literals_in_ast(node):
    string_literals = []

    if isinstance(node, solnodes.Literal) and isinstance(node.value, str) and len(node.value) > 1:
        string_literals.append(node)

    for child in node.get_children():
        if child is not None:
            string_literals.extend(find_string_literals_in_ast(child))

    return string_literals


import re

INDENT_REG = re.compile(r'[ \t]+$')


def get_trailing_whitespace(s):
    match = INDENT_REG.search(s)
    if match:
        return match.group(0)
    else:
        return ""


LINE_REG = re.compile("\r?\n")


def indent_by(s, indentation):
    return ("\n" + indentation).join(LINE_REG.split(s))


def generate_obfuscated_code(obfuscated_expr):
    if isinstance(obfuscated_expr, solnodes.BinaryOp):
        left_code = generate_obfuscated_code(obfuscated_expr.left)
        right_code = generate_obfuscated_code(obfuscated_expr.right)
        return f"{left_code} {obfuscated_expr.op.value} {right_code}"

    elif isinstance(obfuscated_expr, solnodes.Literal):
        return f'"{obfuscated_expr.value}"' if isinstance(obfuscated_expr.value, str) else str(obfuscated_expr.value)

    else:
        return "/* obfuscated_string */"


def modify_text_with_obfuscation(src_code, obfuscations):
    reverse_sorted_obfuscations = sorted(obfuscations, key=lambda x: -x.start_index)
    current_source_code = src_code

    for obf in reverse_sorted_obfuscations:
        left_part = current_source_code[:obf.start_index]
        right_part = current_source_code[obf.end_index:]

        obfuscated_code = generate_obfuscated_code(obf.obfuscated_expr)

        whitespace = get_trailing_whitespace(left_part)

        formatted_obfuscation = indent_by(obfuscated_code, whitespace)

        current_source_code = left_part + formatted_obfuscation + right_part

    return current_source_code


def obfuscate_file(file_name):
    try:
        file_sym_info = sym_builder.process_or_find_from_base_dir(file_name)
        loaded_src = vfs.sources[file_name]

        ast1_nodes, src_code = loaded_src.ast, loaded_src.contents

        obfuscations = []

        for node in ast1_nodes:
            if not node:
                continue

            string_literals = find_string_literals_in_ast(node)

            for literal in string_literals:
                if should_obfuscate_literal(literal):
                    obfuscated_expr = obfuscate_string_literal(literal)
                    obfuscations.append(Obfuscation(
                        original_literal=literal,
                        obfuscated_expr=obfuscated_expr,
                        start_index=literal.start_buffer_index,
                        end_index=literal.end_buffer_index
                    ))

        if obfuscations:
            obfuscated_code = modify_text_with_obfuscation(src_code, obfuscations)
            print(f"// Obfuscated version of {file_name}")
            print(obfuscated_code)
        else:
            print(f"No string literals found to obfuscate in {file_name}")
    except Exception as e:
        print(f"Error processing file {file_name}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":

    random.seed(42)

    for f in files_to_obfuscate:
        obfuscate_file(f)