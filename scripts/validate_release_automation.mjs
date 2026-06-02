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
const mcpNpmPackage = JSON.parse(await readText("fovux-mcp-npm/package.json"));
const studioPackage = JSON.parse(await readText("fovux-studio/package.json"));
const workflowsDir = new URL(".github/workflows/", root);
const workflowsPath = fileURLToPath(workflowsDir);
const workflowNames = await readdir(workflowsDir);
const STUDIO_PACKAGE_NAME = "fovuxstudiokit";
const STUDIO_IDENTIFIER = "oaslananka.fovuxstudiokit";
const STUDIO_VSIX = "fovuxstudiokit.vsix";
const STUDIO_DISPLAY_NAME = "Fovux Studio Kit";
const OVSX_VERSION = "1.0.0";
const MCP_NPM_PACKAGE_NAME = "fovux-mcp";
const FIRST_PUBLIC_RELEASE_VERSION = "1.0.0";
const studioIdentifier = `${studioPackage.publisher}.${studioPackage.name}`;
const studioPackageVersion = studioPackage.version;
const mcpPackageVersion = pyprojectValue(mcpPyproject, "version");
const mcpNpmPackageVersion = mcpNpmPackage.version;

const expectedPackages = {
  "fovux-mcp": {
    releaseType: "python",
    component: "fovux-mcp",
    packageName: pyprojectValue(mcpPyproject, "name"),
    version: mcpPackageVersion,
    changelog: "CHANGELOG.md",
  },
  "fovux-mcp-npm": {
    releaseType: "node",
    component: "fovux-mcp-npm",
    packageName: MCP_NPM_PACKAGE_NAME,
    version: mcpNpmPackageVersion,
    changelog: "CHANGELOG.md",
  },
  "fovux-studio": {
    releaseType: "node",
    component: "fovux-studio",
    packageName: STUDIO_PACKAGE_NAME,
    version: studioPackageVersion,
    changelog: "CHANGELOG.md",
  },
};

if (studioPackage.displayName !== STUDIO_DISPLAY_NAME) {
  fail(`Fovux Studio displayName must be ${STUDIO_DISPLAY_NAME}`);
}
if (mcpNpmPackage.name !== MCP_NPM_PACKAGE_NAME) {
  fail(`Fovux MCP npm wrapper package name must be ${MCP_NPM_PACKAGE_NAME}`);
}
if (mcpNpmPackageVersion !== mcpPackageVersion) {
  fail("Fovux MCP npm wrapper version must match the Python package version");
}
if (mcpNpmPackage.bin?.["fovux-mcp"] !== "bin/fovux-mcp.js") {
  fail("Fovux MCP npm wrapper must expose the fovux-mcp command");
}
if (mcpNpmPackage.bin?.fovux !== "bin/fovux-mcp.js") {
  fail("Fovux MCP npm wrapper must expose the fovux command");
}
if (studioPackage.name !== STUDIO_PACKAGE_NAME) {
  fail(`Fovux Studio package name must be ${STUDIO_PACKAGE_NAME}`);
}
if (
  typeof studioPackageVersion !== "string" ||
  studioPackageVersion.length === 0
) {
  fail("Fovux Studio package version must be defined");
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
  if (actual["release-as"] !== FIRST_PUBLIC_RELEASE_VERSION) {
    fail(
      `${path} release-as must pin the first public release to ${FIRST_PUBLIC_RELEASE_VERSION}`,
    );
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
  "chore(release): release${component}"
) {
  fail(
    "group release pull request title must preserve release-please's parseable grouped PR title",
  );
}

let hasMcpLinkedVersions = false;
for (const plugin of config.plugins ?? []) {
  if (plugin.type === "linked-versions") {
    const components = plugin.components ?? [];
    if (components.includes("fovux-studio")) {
      fail("fovux-studio must not be part of release-please linked-versions");
    }
    if (
      components.includes("fovux-mcp") &&
      components.includes("fovux-mcp-npm")
    ) {
      hasMcpLinkedVersions = true;
    }
  }
}
if (!hasMcpLinkedVersions) {
  fail("fovux-mcp and fovux-mcp-npm must use release-please linked-versions");
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
    'gh release upload "$RELEASE_TAG" --clobber',
    "publish-npm-wrapper",
    "npm publish --provenance --access public",
  ]) {
    if (!releaseWorkflow.includes(required)) {
      fail(`release workflow must reference ${required}`);
    }
  }
  for (const forbidden of [
    "fovux-studio.vsix",
    "ovsx@0.10.11",
    "ovsx@0.10.12",
  ]) {
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
    "studio-release-assets",
    "channel:",
    'gh release upload "$release_tag" --clobber',
    `OVSX_VERSION: "${OVSX_VERSION}"`,
    "runs-on: ubuntu-24.04",
  ]) {
    if (!publishWorkflow.includes(required)) {
      fail(`production publish workflow must reference ${required}`);
    }
  }
  if (/runs-on:\s*\[?\s*["']?self-hosted\b/.test(publishWorkflow)) {
    fail("production publish workflow must use GitHub-hosted runners");
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
  ["workflow_dispatch", "inputs", "tag"].join("."),
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
  `Release automation config is manifest-driven, release-version-input free, first-public pinned to ${FIRST_PUBLIC_RELEASE_VERSION}, and targets ${STUDIO_IDENTIFIER}.`,
);
