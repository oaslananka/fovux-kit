export interface TrainingFormValues {
  runName: string;
  datasetPath: string;
  model: string;
  epochs: number;
  batch: number;
  imgsz: number;
  device: string;
  tags: string;
  extraArgs: string;
  force: boolean;
  maxConcurrentRuns: number;
}

export function buildTrainingPayload(values: TrainingFormValues): Record<string, unknown> {
  const datasetPath = values.datasetPath.trim();
  if (!datasetPath) {
    throw new Error("Dataset path is required.");
  }

  let parsedExtra: Record<string, unknown> = {};
  if (values.extraArgs.trim()) {
    const raw = JSON.parse(values.extraArgs) as unknown;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      throw new Error("Extra args must be a JSON object.");
    }
    parsedExtra = raw as Record<string, unknown>;
  }

  return {
    dataset_path: datasetPath,
    model: values.model.trim(),
    epochs: values.epochs,
    batch: values.batch,
    imgsz: values.imgsz,
    device: values.device,
    tags: values.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
    extra_args: parsedExtra,
    name: values.runName.trim() || undefined,
    force: values.force,
    max_concurrent_runs: Math.max(0, Math.floor(values.maxConcurrentRuns)),
  };
}

export interface TrainingPreflightEvaluation {
  blocked: boolean;
  errorMessage: string | null;
  approvalReason: string | undefined;
}

export function evaluateTrainingPreflight(
  preflight: Record<string, unknown>,
  force: boolean
): TrainingPreflightEvaluation {
  const blockers = Array.isArray(preflight["blockers"])
    ? (preflight["blockers"] as unknown[]).map(String)
    : [];
  const nextActions = Array.isArray(preflight["next_actions"])
    ? (preflight["next_actions"] as unknown[]).map(String)
    : [];
  const hasBlockers = preflight["ready"] === false || blockers.length > 0;

  return {
    blocked: hasBlockers && !force,
    errorMessage:
      hasBlockers && !force
        ? [
            "Training preflight blocked launch.",
            ...blockers.map((item) => `- ${item}`),
            ...nextActions.map((item) => `Next: ${item}`),
          ].join("\n")
        : null,
    approvalReason:
      hasBlockers && force
        ? `Studio force override after preflight blockers: ${blockers.join("; ")}`
        : undefined,
  };
}
