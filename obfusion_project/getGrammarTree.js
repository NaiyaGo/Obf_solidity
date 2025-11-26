// const parser = require("@solidity-parser/parser");
// const fs = require("fs");
// const path = require("path");



// // 项目目录
// const projectDir = path.resolve("./solidity_project");
// // Solidity 文件路径
// const solidityFilePath = path.join(projectDir, "contracts","TestContract.sol");



// // 读取源码
// const solidityFileSourceCode = fs.readFileSync(solidityFilePath, "utf8");

// // 解析 AST
// let astNodes;
// astNodes = parser.parse(solidityFileSourceCode, { loc: true, range: true });

// // 等待python调用
// console.log(JSON.stringify(astNodes));

const parser = require("@solidity-parser/parser");
const fs = require("fs");
const path = require("path");

// 用法：node getGrammarTree.js <solidity-file> 
// 也支持：node getGrammarTree.js -      （从 stdin 读取源码）
// 若不传参，则回退到 ./solidity_project/contracts/TestContract.sol

const argPath = process.argv[2];

function readSource(fpOrDash) {
  if (fpOrDash === "-") {
    // 从 stdin 读取
    try {
      return fs.readFileSync(0, "utf8"); // 0 = stdin
    } catch (e) {
      console.error(JSON.stringify({ error: "Failed to read from stdin", detail: e.message }));
      process.exit(1);
    }
  }
  const abs = path.isAbsolute(fpOrDash) ? fpOrDash : path.resolve(fpOrDash);
  try {
    return fs.readFileSync(abs, "utf8");
  } catch (e) {
    console.error(JSON.stringify({ error: `Failed to read file: ${abs}`, detail: e.message }));
    process.exit(1);
  }
}

let targetPath;
if (argPath && argPath !== "-") {
  targetPath = path.isAbsolute(argPath) ? argPath : path.resolve(argPath);
} else if (argPath === "-") {
  targetPath = "-"; // stdin
} else {
  // 兼容旧逻辑：默认路径
  const projectDir = path.resolve("./solidity_project");
  targetPath = path.join(projectDir, "contracts", "TestContract.sol");
}

const source = readSource(targetPath);

try {
  // loc/range 都要打开，保持你 Python 侧访问的字段一致
  const ast = parser.parse(source, { loc: true, range: true, tolerant: true });
  process.stdout.write(JSON.stringify(ast));
} catch (err) {
  // solidity-parser 出错时 location 可能有行列信息
  const out = { error: err.message, location: err.location || null, stack: undefined };
  console.error(JSON.stringify(out));
  process.exit(1);
}
