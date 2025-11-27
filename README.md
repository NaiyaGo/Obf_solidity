# Obfusecator of solidity file

### dependency
solidity-parser
```
pip install -r requirements.txt
```

### quickstart

```
python3 ./obfusion_project/main.py --enable cf,deadcode,literal --file TheContract.sol,TestContract.sol
```

### usage
```
usage: main.py [-h] [--file FILE] [--dir DIR] [--out OUT] [--enable ENABLE] [--seed SEED] [--cf-density CF_DENSITY]
               [--dead-density DEAD_DENSITY] [--literal-density LITERAL_DENSITY] [--layout-shuffle LAYOUT_SHUFFLE]

Solidity Obfuscation Pipeline (scaffold)

options:
  -h, --help            show this help message and exit
  --file FILE           指定.sol 文件, 以,分割
  --dir DIR             指定目录 (递归处理 .sol)
  --out OUT             输出目录
  --enable ENABLE       启用的 Pass 列表(逗号分隔) cf,dead,literal,layout,chaos
  --seed SEED
  --cf-density CF_DENSITY
                        ControlFlow 注入密度（占位）
  --dead-density DEAD_DENSITY
                        DeadCode 注入密度（占位）
  --literal-density LITERAL_DENSITY
                        String literal obfuscation rate (0.0-1.0)
  --layout-shuffle LAYOUT_SHUFFLE
                        Layout 重排强度（占位）
```

### project structure
```
|- obfusion_project
|---|- obf_controlflow.py
|---|- obf_deadcode.py
|---|- obf_layout.py
|- solidity_project
|---|- lib
|---|- src
|   |---|- TheContract.sol
|   |---|- TestContract.sol
```