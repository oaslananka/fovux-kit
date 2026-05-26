import * as path from "node:path";

import { describe, expect, it } from "vitest";

import "./helpers/vscodeMock";
import { DataYamlCodeLensProvider } from "../../src/codelens/dataYamlCodeLens";

describe("DataYamlCodeLensProvider", () => {
  it("creates dataset actions for YOLO data.yaml files", () => {
    const provider = new DataYamlCodeLensProvider();
    const datasetPath = path.join("workspace", "dataset");

    const lenses = provider.provideCodeLenses({
      fileName: path.join(datasetPath, "data.yaml"),
      uri: { fsPath: path.join(datasetPath, "data.yaml") },
    } as never);

    expect(lenses.map((lens) => lens.command?.command)).toEqual([
      "fovux.validateDataset",
      "fovux.openDatasetInspector",
      "fovux.startTraining",
    ]);
    expect(lenses[0]?.command?.arguments).toEqual([datasetPath]);
  });

  it("ignores unrelated yaml files", () => {
    const provider = new DataYamlCodeLensProvider();

    expect(
      provider.provideCodeLenses({
        fileName: path.join("workspace", "dataset", "classes.yaml"),
        uri: { fsPath: path.join("workspace", "dataset", "classes.yaml") },
      } as never),
    ).toEqual([]);
  });
});
