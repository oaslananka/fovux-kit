import * as fs from "node:fs/promises";
import * as path from "node:path";

import { DatasetSample, DatasetSampleBox } from "../shared/types";

interface BuildDatasetSamplesOptions {
  datasetPath: string;
  samplePaths: string[];
  classNames: string[];
  toWebviewUri: (samplePath: string) => string;
}

export async function buildDatasetSamples(
  options: BuildDatasetSamplesOptions
): Promise<DatasetSample[]> {
  const samples = await Promise.all(
    options.samplePaths.slice(0, 8).map(async (samplePath) => {
      const boxes = await loadSampleBoxes(options.datasetPath, samplePath, options.classNames);
      return {
        path: samplePath,
        uri: options.toWebviewUri(samplePath),
        boxes,
      } satisfies DatasetSample;
    })
  );
  return samples;
}

async function loadSampleBoxes(
  datasetPath: string,
  samplePath: string,
  classNames: string[]
): Promise<DatasetSampleBox[]> {
  const labelPath = resolveLabelPath(datasetPath, samplePath);
  if (labelPath === null) {
    return [];
  }

  try {
    const raw = await fs.readFile(labelPath, "utf-8");
    return raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .flatMap((line) => {
        const parts = line.split(/\s+/);
        if (parts.length < 5) {
          return [];
        }
        const classId = Number(parts[0]);
        const centerX = Number(parts[1]);
        const centerY = Number(parts[2]);
        const width = Number(parts[3]);
        const height = Number(parts[4]);
        if ([classId, centerX, centerY, width, height].some((value) => Number.isNaN(value))) {
          return [];
        }
        return [
          {
            classId,
            className: classNames[classId] ?? `class_${classId}`,
            x: clamp(centerX - width / 2),
            y: clamp(centerY - height / 2),
            width: clamp(width),
            height: clamp(height),
          } satisfies DatasetSampleBox,
        ];
      });
  } catch {
    return [];
  }
}

export function resolveLabelPath(datasetPath: string, samplePath: string): string | null {
  const pathApi = usesWindowsPath(datasetPath) || usesWindowsPath(samplePath) ? path.win32 : path;
  const imagesRoot = pathApi.join(datasetPath, "images");
  if (!samplePath.startsWith(imagesRoot)) {
    return null;
  }

  const relative = pathApi.relative(imagesRoot, samplePath);
  const withoutExtension = relative.replace(/\.[^.]+$/, ".txt");
  return pathApi.join(datasetPath, "labels", withoutExtension);
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function usesWindowsPath(nextPath: string): boolean {
  return /^[A-Za-z]:[\\/]/.test(nextPath) || nextPath.includes("\\");
}
