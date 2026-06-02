#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");

const packageJson = JSON.parse(
  readFileSync(join(__dirname, "..", "package.json"), "utf8"),
);
const pythonPackage =
  process.env.FOVUX_MCP_PYTHON_PACKAGE || `fovux-mcp==${packageJson.version}`;
const passthroughArgs = process.argv.slice(2);
const uvxArgs = ["--from", pythonPackage, "fovux-mcp", ...passthroughArgs];

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.error?.code === "ENOENT") return null;
  if (result.error) {
    console.error(`Failed to start ${command}: ${result.error.message}`);
    process.exit(1);
  }
  return result.status ?? 1;
}

const uvxCommands = process.platform === "win32" ? ["uvx.exe", "uvx"] : ["uvx"];
for (const command of uvxCommands) {
  const status = run(command, uvxArgs);
  if (status !== null) process.exit(status);
}

const uvCommands = process.platform === "win32" ? ["uv.exe", "uv"] : ["uv"];
for (const command of uvCommands) {
  const status = run(command, ["tool", "run", ...uvxArgs]);
  if (status !== null) process.exit(status);
}

console.error(
  "fovux-mcp requires uv or uvx on PATH. Install uv from https://docs.astral.sh/uv/.",
);
process.exit(127);
