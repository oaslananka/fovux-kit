import * as fs from "node:fs";
import * as path from "node:path";

import { describe, expect, it } from "vitest";

const WEBVIEW_ROOT = path.join(process.cwd(), "src", "webviews");
const ENTRYPOINTS = ["dashboard/main.tsx", "datasetInspector/main.tsx"];
const IMPORT_PATTERN = /from\s+["'](\.[^"']+)["']/g;
const RESOLUTION_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx"];

describe("webview component imports", () => {
  it("resolve local component modules referenced by entrypoints", () => {
    for (const entrypoint of ENTRYPOINTS) {
      const source = readWebviewSource(entrypoint);
      for (const importPath of extractRelativeImports(source)) {
        expect(
          resolveImport(entrypoint, importPath),
          `${entrypoint}:${importPath}`,
        ).not.toBeNull();
      }
    }
  });
});

function readWebviewSource(entrypoint: string): string {
  return fs.readFileSync(
    path.join(WEBVIEW_ROOT, ...entrypoint.split("/")),
    "utf8",
  );
}

function extractRelativeImports(source: string): string[] {
  return [...source.matchAll(IMPORT_PATTERN)]
    .map((match) => match[1])
    .filter(isString);
}

function resolveImport(entrypoint: string, importPath: string): string | null {
  const basePath = path.join(
    WEBVIEW_ROOT,
    path.dirname(entrypoint),
    importPath,
  );
  for (const candidate of expandImportCandidates(basePath)) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function expandImportCandidates(basePath: string): string[] {
  if (path.extname(basePath)) {
    return [basePath];
  }
  const files = RESOLUTION_EXTENSIONS.map(
    (extension) => `${basePath}${extension}`,
  );
  const indexes = RESOLUTION_EXTENSIONS.map((extension) =>
    path.join(basePath, `index${extension}`),
  );
  return [...files, ...indexes];
}

function isString(value: string | undefined): value is string {
  return typeof value === "string";
}
