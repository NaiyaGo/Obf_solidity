import sys
import json
import subprocess
from typing import Any, Optional, ClassVar, Final

if len(sys.argv) < 2:
    print("请提供文件路径参数")
    sys.exit(1)

file_path = sys.argv[1]
print(f"接收到的文件路径: {file_path}")



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

with open("pureTree.txt", "w", encoding="utf-8") as f:
    json.dump(solidity_ast, f, ensure_ascii=False, indent=4)
