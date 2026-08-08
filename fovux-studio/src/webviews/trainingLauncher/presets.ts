import type { UserPreset } from "../shared/types";

export interface TrainingPreset {
  id: "fast_prototype" | "production" | "mobile_edge" | "accuracy_max";
  label: string;
  description: string;
  config: {
    model: string;
    epochs: number;
    batch: number;
    imgsz: number;
    device: string;
    tags: string;
  };
}

export const TRAINING_PRESETS: TrainingPreset[] = [
  {
    id: "fast_prototype",
    label: "Fast Prototype",
    description: "30 epochs, compact model, optimized for a quick sanity-check.",
    config: {
      model: "yolov8n.pt",
      epochs: 30,
      batch: 32,
      imgsz: 416,
      device: "auto",
      tags: "prototype, quick-check",
    },
  },
  {
    id: "production",
    label: "Production",
    description: "Balanced accuracy and throughput for a durable local baseline.",
    config: {
      model: "yolov8m.pt",
      epochs: 150,
      batch: 16,
      imgsz: 640,
      device: "auto",
      tags: "production, baseline",
    },
  },
  {
    id: "mobile_edge",
    label: "Mobile Edge",
    description: "Keeps the artifact export-friendly for smaller edge targets.",
    config: {
      model: "yolov8n.pt",
      epochs: 100,
      batch: 32,
      imgsz: 320,
      device: "auto",
      tags: "edge, int8-ready",
    },
  },
  {
    id: "accuracy_max",
    label: "Accuracy Max",
    description: "Longer run for the highest local mAP that still fits common workstations.",
    config: {
      model: "yolov8x.pt",
      epochs: 300,
      batch: 8,
      imgsz: 960,
      device: "auto",
      tags: "accuracy, long-run",
    },
  },
];

export function estimateTrainingMinutes(epochs: number, batch: number, imgsz: number): number {
  const workload = epochs * Math.max(imgsz / 320, 1);
  const throughputFactor = Math.max(batch, 1) / 8;
  return Math.max(5, Math.round((workload / throughputFactor) * 0.75));
}

export function parseImportedPresets(rawJson: string): UserPreset[] {
  const parsed = JSON.parse(rawJson) as unknown;
  let candidates: unknown[] = [];

  if (Array.isArray(parsed)) {
    candidates = parsed;
  } else if (parsed && typeof parsed === "object") {
    const presets = (parsed as { presets?: unknown }).presets;
    if (Array.isArray(presets)) {
      candidates = presets;
    }
  }

  return candidates.filter(isUserPreset);
}

function isUserPreset(value: unknown): value is UserPreset {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  const config = record["config"];
  if (!config || typeof config !== "object") {
    return false;
  }
  const cfg = config as Record<string, unknown>;
  return (
    typeof record["name"] === "string" &&
    typeof record["createdAt"] === "string" &&
    typeof cfg["model"] === "string" &&
    typeof cfg["epochs"] === "number" &&
    typeof cfg["batch"] === "number" &&
    typeof cfg["imgsz"] === "number" &&
    typeof cfg["device"] === "string" &&
    typeof cfg["tags"] === "string" &&
    typeof cfg["extraArgs"] === "string" &&
    typeof cfg["maxConcurrentRuns"] === "number"
  );
}

export function mergePresets(imported: UserPreset[], current: UserPreset[]): UserPreset[] {
  return [
    ...imported,
    ...current.filter((candidate) => !imported.some((preset) => preset.name === candidate.name)),
  ].slice(0, 20);
}
