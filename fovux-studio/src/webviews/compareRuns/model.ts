export type PromotionState = "draft" | "candidate" | "approved" | "deployed";

export interface ComparedRun {
  run_id: string;
  status: string;
  model: string;
  epochs: number;
  current_epoch?: number | null;
  best_map50?: number | null;
  best_map50_95?: number | null;
  precision?: number | null;
  recall?: number | null;
  latency_ms?: number | null;
  model_size_mb?: number | null;
  config?: Record<string, unknown>;
  dataset_fingerprint?: string | null;
  export_target?: string | null;
  pareto_optimal?: boolean;
  promotion_state?: PromotionState;
  run_path: string;
}

export interface CompareResult {
  compared_runs: ComparedRun[];
  best_run_id: string | null;
  report_path: string;
  chart_path: string;
  config_diffs: Record<string, Record<string, unknown>>;
  pareto_frontier_run_ids: string[];
  model_cards: Record<string, string>;
  suggested_next_experiment: string;
}

export type CompareSortOrder = "asc" | "desc";

export function sortComparedRuns(
  runs: ComparedRun[],
  sortBy: string,
  sortOrder: CompareSortOrder
): ComparedRun[] {
  return [...runs].sort((a, b) => {
    const valA = a[sortBy as keyof ComparedRun];
    const valB = b[sortBy as keyof ComparedRun];

    if (valA === undefined || valA === null) return sortOrder === "desc" ? 1 : -1;
    if (valB === undefined || valB === null) return sortOrder === "desc" ? -1 : 1;

    if (typeof valA === "number" && typeof valB === "number") {
      return sortOrder === "desc" ? valB - valA : valA - valB;
    }
    if (typeof valA === "string" && typeof valB === "string") {
      return sortOrder === "desc" ? valB.localeCompare(valA) : valA.localeCompare(valB);
    }
    return 0;
  });
}

export function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(4) : "n/a";
}

const PROMOTION_TAGS = new Set(["candidate", "approved", "deployed"]);

export function buildPromotionTags(currentTags: string[], newState: PromotionState): string[] {
  const baseTags = currentTags.filter((tag) => !PROMOTION_TAGS.has(tag.toLowerCase()));
  return newState === "draft" ? baseTags : [...baseTags, newState];
}

export function applyPromotionState(
  result: CompareResult,
  runId: string,
  newState: PromotionState
): CompareResult {
  return {
    ...result,
    compared_runs: result.compared_runs.map((run) =>
      run.run_id === runId ? { ...run, promotion_state: newState } : run
    ),
  };
}
