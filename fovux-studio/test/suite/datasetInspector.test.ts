import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import { describe, expect, it } from "vitest";

import {
  buildDatasetSamples,
  resolveLabelPath,
} from "../../src/webviews/datasetInspector/sampleData";

describe("dataset inspector sample data", () => {
  it("resolves label paths next to YOLO image splits", () => {
    expect(
      resolveLabelPath("C:\\datasets\\demo", "C:\\datasets\\demo\\images\\val\\sample.jpg")
    ).toContain("labels");
  });

  it("loads normalized boxes for sample previews", async () => {
    const datasetRoot = fs.mkdtempSync(path.join(os.tmpdir(), "fovux-dataset-preview-"));
    const imageDir = path.join(datasetRoot, "images", "val");
    const labelDir = path.join(datasetRoot, "labels", "val");
    fs.mkdirSync(imageDir, { recursive: true });
    fs.mkdirSync(labelDir, { recursive: true });
    const samplePath = path.join(imageDir, "sample.jpg");
    fs.writeFileSync(samplePath, "fake-image");
    fs.writeFileSync(path.join(labelDir, "sample.txt"), "0 0.5 0.5 0.4 0.2\n");

    const samples = await buildDatasetSamples({
      datasetPath: datasetRoot,
      samplePaths: [samplePath],
      classNames: ["cat"],
      toWebviewUri: (nextPath) => `webview://${nextPath}`,
    });

    expect(samples).toHaveLength(1);
    expect(samples[0]?.boxes[0]?.className).toBe("cat");
    expect(samples[0]?.boxes[0]?.width).toBeCloseTo(0.4);
  });
});
