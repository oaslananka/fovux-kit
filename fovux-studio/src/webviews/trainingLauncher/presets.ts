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
