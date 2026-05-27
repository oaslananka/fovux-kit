#!/usr/bin/env node
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = new URL("../", import.meta.url);

async function readText(path) {
  return readFile(new URL(path, root), "utf8");
}

function fail(message) {
  console.error(message);
  process.exitCode = 1;
}

function pyprojectValue(text, key) {
  const match = text.match(new RegExp(`^${key}\\s*=\\s*["']([^"']+)["']`, "m"));
  return match?.[1];
}

const config = JSON.parse(await readText("release-please-config.json"));
const manifest = JSON.parse(await readText(".release-please-manifest.json"));
const mcpPyproject = await readText("fovux-mcp/pyproject.toml");
const studioPackage = JSON.parse(await readText("fovux-studio/package.json"));
const workflowsDir = new URL(".github/workflows/", root);
const workflowsPath = fileURLToPath(workflowsDir);
const workflowNames = await readdir(workflowsDir);
const STUDIO_PACKAGE_NAME = "fovuxstudiokit";
const STUDIO_PACKAGE_VERSION = "1.0.0";
const STUDIO_IDENTIFIER = "oaslananka.fovuxstudiokit";
const STUDIO_VSIX = "fovuxstudiokit.vsix";
const OVSX_VERSION = "0.10.12";
const studioIdentifier = `${studioPackage.publisher}.${studioPackage.name}`;

const expectedPackages = {
  "fovux-mcp": {
    releaseType: "python",
    component: "fovux-mcp",
    packageName: pyprojectValue(mcpPyproject, "name"),
    version: pyprojectValue(mcpPyproject, "version"),
    changelog: "CHANGELOG.md",
  },
  "fovux-studio": {
    releaseType: "node",
    component: "fovux-studio",
    packageName: STUDIO_PACKAGE_NAME,
    version: STUDIO_PACKAGE_VERSION,
    changelog: "CHANGELOG.md",
  },
};

if (studioPackage.displayName !== "Fovux Studio") {
  fail("Fovux Studio displayName must stay stable");
}
if (studioPackage.name !== STUDIO_PACKAGE_NAME) {
  fail(`Fovux Studio package name must be ${STUDIO_PACKAGE_NAME}`);
}
if (studioPackage.version !== STUDIO_PACKAGE_VERSION) {
  fail(`Fovux Studio package version must be ${STUDIO_PACKAGE_VERSION}`);
}
if (studioIdentifier !== STUDIO_IDENTIFIER) {
  fail(`Fovux Studio extension identifier must be ${STUDIO_IDENTIFIER}`);
}

for (const [path, expected] of Object.entries(expectedPackages)) {
  const actual = config.packages?.[path];
  if (!actual) {
    fail(`release-please package entry missing: ${path}`);
    continue;
  }
  if (actual["release-type"] !== expected.releaseType) {
    fail(`${path} release-type must be ${expected.releaseType}`);
  }
  if (actual.component !== expected.component) {
    fail(`${path} component must be ${expected.component}`);
  }
  if (actual["package-name"] !== expected.packageName) {
    fail(`${path} package-name must match package metadata`);
  }
  if (actual["changelog-path"] !== expected.changelog) {
    fail(`${path} changelog-path must be ${expected.changelog}`);
  }
  if (actual["include-component-in-tag"] !== true) {
    fail(`${path} must use component-specific tags`);
  }
  if (manifest[path] !== expected.version) {
    fail(`${path} manifest version must match current package version`);
  }
}

if (config["separate-pull-requests"] !== false) {
  fail("release-please must create one grouped release pull request");
}

if (
  config["group-pull-request-title-pattern"] !==
  "chore(release): release ${component} ${version}"
) {
  fail(
    "group release pull request title must include component and version for release-please tagging",
  );
}

for (const plugin of config.plugins ?? []) {
  if (
    plugin.type === "linked-versions" &&
    (plugin.components ?? []).includes("fovux-studio")
  ) {
    fail("fovux-studio must not be part of release-please linked-versions");
  }
}

const mcpExtraFiles = config.packages?.["fovux-mcp"]?.["extra-files"] ?? [];
for (const requiredPath of [
  "src/fovux/__init__.py",
  "server.json",
  "smithery.yaml",
]) {
  if (
    !mcpExtraFiles.some(
      (entry) =>
        (typeof entry === "string" ? entry : entry.path) === requiredPath,
    )
  ) {
    fail(`fovux-mcp extra-files must update ${requiredPath}`);
  }
}

if (!workflowNames.includes("release-please.yml")) {
  fail("release-please workflow is required");
} else {
  const releaseWorkflow = await readFile(
    join(workflowsPath, "release-please.yml"),
    "utf8",
  );
  if (!releaseWorkflow.includes("python3 scripts/sync_mcp_metadata.py")) {
    fail("release pull request metadata sync must update root MCP metadata");
  }
  if (!releaseWorkflow.includes("fovux-mcp/uv.lock")) {
    fail("release pull request metadata sync must update uv.lock");
  }
  for (const required of [
    STUDIO_IDENTIFIER,
    STUDIO_VSIX,
    `ovsx@${OVSX_VERSION}`,
  ]) {
    if (!releaseWorkflow.includes(required)) {
      fail(`release workflow must reference ${required}`);
    }
  }
  for (const forbidden of ["fovux-studio.vsix", "ovsx@0.10.11"]) {
    if (releaseWorkflow.includes(forbidden)) {
      fail(`release workflow must not reference ${forbidden}`);
    }
  }
}

if (!workflowNames.includes("publish-production.yml")) {
  fail("production publish workflow is required");
} else {
  const publishWorkflow = await readFile(
    join(workflowsPath, "publish-production.yml"),
    "utf8",
  );
  for (const required of [
    STUDIO_IDENTIFIER,
    "extension_identifier",
    `OVSX_VERSION: "${OVSX_VERSION}"`,
  ]) {
    if (!publishWorkflow.includes(required)) {
      fail(`production publish workflow must reference ${required}`);
    }
  }
}

const forbiddenReleaseInputs = [
  ["RELEASE", "VERSION"].join("_"),
  ["INPUT", "VERSION"].join("_"),
  ["github", "event", "inputs", "version"].join("."),
  ["github", "event", "inputs", ["release", "version"].join("_")].join("."),
  ["github", "event", "inputs", "tag"].join("."),
  ["workflow_dispatch", "inputs", "version"].join("."),
  ["workflow_dispatch", "inputs", ["release", "version"].join("_")].join("."),
];

for (const name of workflowNames.filter(
  (item) => item.endsWith(".yml") || item.endsWith(".yaml"),
)) {
  const text = await readFile(join(workflowsPath, name), "utf8");
  for (const forbidden of forbiddenReleaseInputs) {
    if (text.includes(forbidden)) {
      fail(`${name} contains forbidden release input pattern: ${forbidden}`);
    }
  }
}

if (process.exitCode) {
  process.exit(process.exitCode);
}

console.log(
  `Release automation config is manifest-driven, version-input free, and targets ${STUDIO_IDENTIFIER}.`,
);
