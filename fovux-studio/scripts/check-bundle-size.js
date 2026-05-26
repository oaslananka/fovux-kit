/**
 * Deterministic bundle-size check for Fovux Studio.
 *
 * Checks built JavaScript output directly so CI fails on the file that regressed:
 * - out/extension.js: 500 KB
 * - JavaScript files below out/webviews: 1 MB each
 * - *.vsix package, when present: 10 MB
 */

const { existsSync, readdirSync, statSync } = require("node:fs");
const { join, relative, resolve } = require("node:path");

const ROOT = resolve(__dirname, "..");
const LIMITS = {
  extensionBytes: 500 * 1024,
  webviewBytes: 1024 * 1024,
  vsixBytes: 10 * 1024 * 1024,
};

function main() {
  const failures = [];
  const extensionPath = join(ROOT, "out", "extension.js");
  checkRequiredFile(extensionPath, LIMITS.extensionBytes, failures);

  const webviewRoot = join(ROOT, "out", "webviews");
  const webviewFiles = existsSync(webviewRoot) ? findJsFiles(webviewRoot) : [];
  if (webviewFiles.length === 0) {
    failures.push(
      "No webview bundles found under out/webviews. Run `pnpm build` first.",
    );
  }
  for (const file of webviewFiles) {
    checkRequiredFile(file, LIMITS.webviewBytes, failures);
  }

  const vsixFiles = readdirSync(ROOT)
    .filter((file) => file.endsWith(".vsix"))
    .map((file) => join(ROOT, file));
  for (const file of vsixFiles) {
    checkRequiredFile(file, LIMITS.vsixBytes, failures);
  }
  if (vsixFiles.length === 0) {
    console.log("No VSIX package found; skipping package size check.");
  }

  if (failures.length > 0) {
    console.error("Bundle-size check failed:");
    for (const failure of failures) {
      console.error(`  - ${failure}`);
    }
    process.exit(1);
  }

  console.log("Bundle-size check passed.");
}

function checkRequiredFile(file, limitBytes, failures) {
  if (!existsSync(file)) {
    failures.push(
      `${relative(ROOT, file)} is missing. Run \`pnpm build\` first.`,
    );
    return;
  }
  const sizeBytes = statSync(file).size;
  const label = relative(ROOT, file).replace(/\\/g, "/");
  console.log(
    `${label}: ${formatBytes(sizeBytes)} / ${formatBytes(limitBytes)}`,
  );
  if (sizeBytes > limitBytes) {
    failures.push(
      `${label} is ${formatBytes(sizeBytes)}, limit is ${formatBytes(limitBytes)}`,
    );
  }
}

function findJsFiles(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findJsFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".js")) {
      files.push(fullPath);
    }
  }
  return files.sort();
}

function formatBytes(bytes) {
  return `${(bytes / 1024).toFixed(1)} KB`;
}

main();
