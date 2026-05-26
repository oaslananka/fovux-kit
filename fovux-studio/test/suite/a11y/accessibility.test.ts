import * as fs from "node:fs";
import * as path from "node:path";

import { describe, expect, it } from "vitest";

const WEBVIEW_ENTRYPOINTS = [
  "dashboard/main.tsx",
  "datasetInspector/main.tsx",
  "trainingLauncher/main.tsx",
  "exportWizard/main.tsx",
  "annotationEditor/main.tsx",
];

describe("Webview accessibility", () => {
  it("all webview entrypoints render a main landmark", () => {
    for (const entrypoint of WEBVIEW_ENTRYPOINTS) {
      const source = readWebviewSource(entrypoint);
      expect(source, entrypoint).toMatch(/<main\b/);
    }
  });

  it("form controls and icon-free buttons have accessible names", () => {
    for (const entrypoint of WEBVIEW_ENTRYPOINTS) {
      const source = readWebviewSource(entrypoint);
      for (const tag of source.matchAll(
        /<(button|input|select|textarea)\b([^>]*)>/g,
      )) {
        const [, element, attributes] = tag;
        if (!element || !attributes) {
          continue;
        }
        if (hasAccessibleName(attributes)) {
          continue;
        }
        if (element === "input" && /\btype="checkbox"/.test(attributes)) {
          continue;
        }
        if (
          element === "button" &&
          hasVisibleButtonText(source, tag.index ?? 0)
        ) {
          continue;
        }
        expect.fail(
          `${entrypoint} has an unnamed <${element}> control: ${tag[0]}`,
        );
      }
    }
  });
});

function readWebviewSource(entrypoint: string): string {
  return fs.readFileSync(
    path.join(process.cwd(), "src", "webviews", ...entrypoint.split("/")),
    "utf8",
  );
}

function hasAccessibleName(attributes: string): boolean {
  return /\b(aria-label|aria-labelledby|title|id)=/.test(attributes);
}

function hasVisibleButtonText(source: string, buttonStart: number): boolean {
  const close = source.indexOf("</button>", buttonStart);
  if (close === -1) {
    return false;
  }
  let visibleText = "";
  let insideTag = false;
  for (const char of source.slice(buttonStart, close)) {
    if (char === "<") {
      insideTag = true;
      continue;
    }
    if (char === ">") {
      insideTag = false;
      visibleText += " ";
      continue;
    }
    if (!insideTag) {
      visibleText += char;
    }
  }
  return /\w/.test(visibleText.trim());
}
