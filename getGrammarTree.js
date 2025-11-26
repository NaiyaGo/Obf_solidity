const parser = require("@solidity-parser/parser");
const fs = require("fs");
const path = require("path");



// 项目目录
const projectDir = path.resolve("./project");
// Solidity 文件路径
const solidityFilePath = path.join(projectDir, "contracts","TestContract.sol");



// 读取源码
const solidityFileSourceCode = fs.readFileSync(solidityFilePath, "utf8");

// 解析 AST
let astNodes;
astNodes = parser.parse(solidityFileSourceCode, { loc: true, range: true });

// 等待python调用
console.log(JSON.stringify(astNodes));
