# makes this file easily runnable in Pycharm
if __name__ == '__main__':
    pass

import random
import re

from pathlib import Path
from dataclasses import dataclass
from solidity_parser import filesys
from solidity_parser.ast import symtab, ast2builder, solnodes2, solnodes

# this is user input
files_to_obfuscate = ['FloatingFunc.sol', 'TestContract.sol', 'TheContract.sol']
project_dir = Path('solidity_project/contracts')
output_dir = Path('./obf_output')
output_suffix = 'controlflow_obfuscated'

# setup VFS
vfs = filesys.VirtualFileSystem(project_dir, None, [])
sym_builder = symtab.Builder2(vfs)

def get_true_conditions():
    """
        return conditions that are always true
    """
    return [
        "(7 % 3) + 1 == 5",
        "(6 * 2) - 1 == 11",
        "(18 / 3) - 1 != 4",
        "(7 * 3) % 20 == 1",
    ]

def get_false_conditions():
    """
        return conditions that are always false
    """
    return [
        "5 + 3 == 10",
        "12 / 4 != 3",
        "7 * 2 < 10",
        "9 - 4 > 6",
    ]

def get_deadcode():
    """
        return code snippets that do nothing
    """
    return [
        "uint256 uselessVar = 0;",  # Simple unused variable
        "if (1 == 0) { uint256 neverUsed = 42; }",  # Conditional that never executes
        "for (uint256 i = 0; i < 0; i++) { uint256 neverIterated = i; }",  # Unreachable loop
        "require(1 == 0, 'This will never happen');",  # Impossible requirement
        "bytes32 unusedHash = keccak256(abi.encodePacked('dead_code'));",  # Dead hash calculation
    ]

def add_true_condition(code):
    always_true_conditions = get_true_conditions()
    always_false_conditions = get_false_conditions()
    deadcode = get_deadcode()
    fake_logic = ""
    if random.random() < 0.5:
        fake_logic = f"({random.choice(always_true_conditions)})"
    else:
        fake_logic = f"(!({random.choice(always_false_conditions)}))"

    return f"if {fake_logic} {{\n    {code}\n}} else {{\n    {random.choice(deadcode)}\n}}"

def minify_code(code):
    """
    Minify Solidity code by removing all unnecessary spaces and line breaks.
    :param code: Input code
    :return: Minified code
    """
    # Remove all line breaks and multiple spaces
    code = re.sub(r'(?<!\/\/ SPDX-License-Identifier: MIT)\s+', ' ', code)
    # Remove spaces around curly braces and semicolons
    code = re.sub(r'\s*{\s*', '{', code)
    code = re.sub(r'\s*}\s*', '}', code)
    code = re.sub(r'\s*;\s*', ';', code)
    return code.strip()

def shuffle_code_blocks(code):
    """
    Shuffle the order of functions and contract members
    :param code: Input code
    :return: Code with shuffled blocks
    """
    pragma_match = re.search(r'\/\/ SPDX-License-Identifier:.*\n?pragma\s+solidity.*?;', code)
    contract_match = re.search(r'contract\s+\w+\s*\{', code)

    if not pragma_match or not contract_match:
        raise ValueError("Invalid Solidity contract structure.")

    pragma = pragma_match.group()
    contract_def = contract_match.group()

    # Extract the body of the contract
    body_start = contract_match.end()
    body_end = code.rfind("}")
    body_content = code[body_start:body_end].strip()

    # Split contract body into blocks and shuffle
    blocks = re.findall(r'(function[^{}]*{([^{}]*{[^{}]*})*[^{}]*}|mapping.*?;|event.*?;|modifier[^{}]*{([^{}]*{[^{}]*})*[^{}]*}|constructor[^{}]*{([^{}]*{[^{}]*})*[^{}]*}|struct[^{}]*{([^{}]*{[^{}]*})*[^{}]*}|((bool|u?int(8|16|32|64|128|256)?|u?fixed|address|string|byte(s[0-9]*)?|enum)\s+.*?;))', body_content, flags=re.DOTALL)
    random.shuffle(blocks)

    shuffled_body = ''
    for block in blocks:
        shuffled_body += block[0]
    return f"{pragma}{contract_def}{shuffled_body}}}"

@dataclass
class Insertion:
    stmt: solnodes.Stmt
    comment: str

INDENT_REG = re.compile(r'[ \t]+$')

def get_trailing_whitespace(s) -> str:
    match = INDENT_REG.search(s)
    if match:
        return match.group(0)
    else:
        return ""

LINE_REG = re.compile("\r?\n")

def indent_by(s, indentation) -> str:
    return ("\n" + indentation).join(LINE_REG.split(s))


def modify_text(src_code, modifications):
    reverse_sorted_modifications = sorted(modifications, key=lambda x: (-x.stmt.start_location.line, x.stmt.start_location.column))
    current_source_code = src_code

    for ins in reverse_sorted_modifications:
        left = current_source_code[0:ins.stmt.start_buffer_index]
        right = current_source_code[ins.stmt.end_buffer_index:]

        # for formatting the comments nicely
        whitespace = get_trailing_whitespace(left)
        formatted_comment = indent_by(f'{ins.comment}', whitespace)
        current_source_code = left + formatted_comment + '\n' + whitespace + right

    return current_source_code

def obfuscate_code_cf(src_code, ast_nodes, density=0.3):
    """
        For all normal statement, random choose some to add if with true condition
        :src_code: original code
        :ast_nodes: ast tree nodes
    """
    modifications = []

    for node in ast_nodes:
        if not node:
            continue
        for func in node.get_all_children(lambda x: isinstance(x, solnodes.FunctionDefinition)):
            for stmt in func.get_all_children(lambda x: isinstance(x, solnodes.ExprStmt)):
                stmt_code = src_code[stmt.start_buffer_index:stmt.end_buffer_index] # complexify_conditions(src_code)
                # print("Original Statement:", stmt_code)
                if random.random() < density:
                    obf_code = add_true_condition(stmt_code)
                    # print(f"Obfuscated Statement:\n{obf_code}\n")
                    modifications.append(Insertion(stmt, obf_code))
    code = modify_text(src_code, modifications)
    # code = minify_code(code)
    # code = shuffle_code_blocks(code)
    return code


def obfuscate_file(file_name):
    """
        Read a Solidity file, add if statement, and save to a new file.
    """
    # Process the file to get symbol information
    file_sym_info = sym_builder.process_or_find_from_base_dir(file_name)
    loaded_src = vfs.sources[file_name]
    
    ast_nodes = loaded_src.ast
    src_code = loaded_src.contents

    obfuscated_code = obfuscate_code_cf(src_code, ast_nodes)

    # Generate output filename
    file_path = Path(file_name)
    output_name = file_path.stem + output_suffix + file_path.suffix
    output_path = output_dir / output_name
    
    # Write obfuscated code to file
    with open(output_path, 'w') as f:
        f.write(obfuscated_code)

# Run obfuscation
if __name__ == "__main__":
    for f in files_to_obfuscate:
        obfuscate_file(f)