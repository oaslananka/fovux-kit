export interface GuidedWorkflowStage {
  id: string;
  title: string;
  status: "pending" | "ready" | "blocked" | "done";
  mcpToolName: string;
  cliCommand: string;
  requiredInputs: Record<string, string>;
  nextActions: string[];
  remediation: string[];
  offlineDemo: string;
}

export const GUIDED_WORKFLOW_STAGES: GuidedWorkflowStage[] = [
  {
    id: "discover_dataset",
    title: "Discover demo or local dataset",
    status: "ready",
    mcpToolName: "demo_init",
    cliCommand: "fovux-mcp serve --http && fovux-mcp demo_init",
    requiredInputs: { target_path: "demo_workspace or local workspace path" },
    nextActions: ["Initialize demo data", "Open dataset inspector"],
    remediation: ["Run doctor", "Check FOVUX_HOME", "Trust workspace"],
    offlineDemo: "demo_init creates sample data, a demo run, a model, and an export locally.",
  },
  {
    id: "validate_inspect",
    title: "Validate and inspect dataset quality",
    status: "pending",
    mcpToolName: "dataset_validate + dataset_inspect",
    cliCommand: "fovux-mcp dataset_validate --dataset-path <path>",
    requiredInputs: { dataset_path: "Path containing data.yaml" },
    nextActions: ["Review validation result", "Open quality report"],
    remediation: ["Fix missing labels", "Fix class ids", "Retry validation"],
    offlineDemo: "Use demo_workspace/sample_dataset/data.yaml.",
  },
  {
    id: "prepare_dataset",
    title: "Prepare dataset",
    status: "pending",
    mcpToolName: "dataset_find_duplicates + dataset_split + dataset_convert + dataset_augment",
    cliCommand: "fovux-mcp dataset_find_duplicates --dataset-path <path>",
    requiredInputs: { dataset_path: "Validated dataset", output_path: "Optional prepared dataset" },
    nextActions: ["Review duplicate groups", "Create split", "Convert or augment"],
    remediation: ["Adjust dataset layout", "Retry validation"],
    offlineDemo: "Demo data is small enough for offline dry runs.",
  },
  {
    id: "preflight_train",
    title: "Preflight and train",
    status: "pending",
    mcpToolName: "train_preflight + train_start",
    cliCommand: "fovux-mcp train_preflight --dataset-path <path>",
    requiredInputs: {
      dataset_path: "Prepared dataset",
      model: "YOLO checkpoint",
      device: "auto/cpu/cuda",
    },
    nextActions: ["Resolve preflight warnings", "Start training"],
    remediation: ["Lower batch size", "Switch device", "Fix paths"],
    offlineDemo: "Demo run metadata is available without remote services.",
  },
  {
    id: "monitor_evaluate",
    title: "Monitor, evaluate, and compare",
    status: "pending",
    mcpToolName: "train_status + eval_run + eval_compare + run_compare",
    cliCommand: "fovux-mcp train_status --run-id <id>",
    requiredInputs: { run_id: "Training run id" },
    nextActions: ["Open dashboard", "Review metrics", "Compare baseline"],
    remediation: ["Open timeline", "Check logs", "Review artifacts"],
    offlineDemo: "demo_run_01 contains sample metrics and artifacts.",
  },
  {
    id: "export_deploy",
    title: "Export and deployment advice",
    status: "pending",
    mcpToolName:
      "export_onnx + benchmark_latency + deployment_advise + export_reproducibility_bundle",
    cliCommand: "fovux-mcp export_onnx --checkpoint <best.pt>",
    requiredInputs: { checkpoint: "Model checkpoint", target_profile: "edge target profile" },
    nextActions: ["Export artifact", "Benchmark target", "Generate bundle"],
    remediation: ["Check export dependency", "Use smaller image size", "Review target limits"],
    offlineDemo: "demo_model.onnx is available after demo initialization.",
  },
];
