/**
 * GENERATED FILE. Run `task studio:lm-tools:generate` after backend schema changes.
 * Source: fovux-mcp/tests/snapshots/mcp_tool_schemas.json
 * Overrides: fovux-studio/src/fovux/tools/overrides.json
 */
import type { GranularToolDefinition } from "./types";

export const GRANULAR_TOOLS = [
  {
    name: "fovux_inspect_dataset",
    toolReferenceName: "fovux_dataset_inspect",
    displayName: "Inspect Dataset",
    userDescription: "Run Fovux Inspect Dataset using the local fovux-mcp server.",
    modelDescription:
      "Produce comprehensive statistics and quality metrics for a dataset. Use when you need to check class balance, Gini index, image sizes, or get an auto-fix recommendation plan. DO NOT use for deep structural checks (use fovux_dataset_validate instead) or perceptual duplicate search (use fovux_dataset_find_duplicates).",
    tags: ["dataset"],
    canBeReferencedInPrompt: true,
    mcpToolName: "dataset_inspect",
    inputSchema: {
      additionalProperties: false,
      properties: {
        dataset_path: {
          type: "string",
        },
        format: {
          default: "auto",
          type: "string",
        },
        include_samples: {
          default: true,
          type: "boolean",
        },
        max_images_analyzed: {
          default: 10000,
          type: "integer",
        },
      },
      required: ["dataset_path"],
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
  {
    name: "fovux_validate_dataset",
    toolReferenceName: "fovux_dataset_validate",
    displayName: "Validate Dataset",
    userDescription: "Run Fovux Validate Dataset using the local fovux-mcp server.",
    modelDescription:
      "Validate a YOLO/COCO dataset for structural correctness. Checks data.yaml, image-label pairing, and annotation format. Use to ensure the dataset is ready for training. DO NOT use if you only want descriptive statistics (use fovux_dataset_inspect instead).",
    tags: ["dataset"],
    canBeReferencedInPrompt: false,
    mcpToolName: "dataset_validate",
    inputSchema: {
      additionalProperties: false,
      properties: {
        check_bbox_bounds: {
          default: true,
          type: "boolean",
        },
        check_class_id_range: {
          default: true,
          type: "boolean",
        },
        check_image_readable: {
          default: true,
          type: "boolean",
        },
        dataset_path: {
          type: "string",
        },
        format: {
          default: "auto",
          type: "string",
        },
        strict: {
          default: false,
          type: "boolean",
        },
      },
      required: ["dataset_path"],
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
  {
    name: "fovux_find_dataset_duplicates",
    toolReferenceName: "fovux_dataset_find_duplicates",
    displayName: "Find Dataset Duplicates",
    userDescription: "Run Fovux Find Dataset Duplicates using the local fovux-mcp server.",
    modelDescription:
      "Detect duplicate or near-duplicate images in a YOLO dataset using perceptual hashing. Use to clean redundant training data and resolve split leakage. DO NOT use for general file comparison or structural validation.",
    tags: ["dataset"],
    canBeReferencedInPrompt: false,
    mcpToolName: "dataset_find_duplicates",
    inputSchema: {
      additionalProperties: false,
      properties: {
        across_splits: {
          default: true,
          type: "boolean",
        },
        algorithm: {
          default: "phash",
          type: "string",
        },
        dataset_path: {
          type: "string",
        },
        hamming_threshold: {
          default: 5,
          type: "integer",
        },
      },
      required: ["dataset_path"],
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
  {
    name: "fovux_check_annotation_quality",
    toolReferenceName: "fovux_annotation_quality_check",
    displayName: "Annotation Quality Check",
    userDescription: "Run Fovux Annotation Quality Check using the local fovux-mcp server.",
    modelDescription:
      "Run targeted heuristic checks for common bounding box anomalies (out of bounds, extremely tiny, highly overlapping, empty). Use to clean up annotation quality before training. DO NOT use for general dataset structure (use fovux_dataset_validate).",
    tags: ["dataset"],
    canBeReferencedInPrompt: false,
    mcpToolName: "annotation_quality_check",
    inputSchema: {
      additionalProperties: false,
      properties: {
        checks: {
          anyOf: [
            {
              items: {
                type: "string",
              },
              type: "array",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        dataset_path: {
          type: "string",
        },
      },
      required: ["dataset_path"],
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
  {
    name: "fovux_start_train",
    toolReferenceName: "fovux_train_start",
    displayName: "Start Training",
    userDescription: "Run Fovux Start Training using the local fovux-mcp server.",
    modelDescription:
      "Launch a new YOLO training run as a non-blocking background subprocess. Use this to start training after preflight/validation checks are successful. DO NOT use if there is an active training run unless force=True or max_concurrent_runs is increased.",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    confirmationKind: "train_start",
    mcpToolName: "train_start",
    inputSchema: {
      additionalProperties: false,
      properties: {
        batch: {
          default: 16,
          type: "integer",
        },
        dataset_path: {
          type: "string",
        },
        device: {
          default: "auto",
          type: "string",
        },
        device_policy: {
          default: "any",
          type: "string",
        },
        epochs: {
          default: 100,
          type: "integer",
        },
        extra_args: {
          anyOf: [
            {
              additionalProperties: true,
              type: "object",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        force: {
          default: false,
          type: "boolean",
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
        max_concurrent_runs: {
          default: 1,
          type: "integer",
        },
        max_disk_usage_gb: {
          anyOf: [
            {
              type: "number",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        max_runtime_seconds: {
          anyOf: [
            {
              type: "integer",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        model: {
          default: "yolov8n.pt",
          type: "string",
        },
        name: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        options: {
          anyOf: [
            {
              additionalProperties: true,
              type: "object",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        preflight_approval_reason: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        tags: {
          anyOf: [
            {
              items: {
                type: "string",
              },
              type: "array",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        task: {
          default: "detect",
          type: "string",
        },
      },
      required: ["dataset_path"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "run:start",
    policyCategory: "long_running",
  },
  {
    name: "fovux_preflight_train",
    toolReferenceName: "fovux_train_preflight",
    displayName: "Training Preflight Check",
    userDescription: "Run Fovux Training Preflight Check using the local fovux-mcp server.",
    modelDescription:
      "Run safety and diagnostic preflight checks before launching training. Checks dataset validity, model source, device availability, disk budgets, and run directory collisions. Use to prevent runtime training failures. DO NOT use to launch training (use fovux_train_start instead).",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    mcpToolName: "train_preflight",
    inputSchema: {
      additionalProperties: false,
      properties: {
        batch: {
          default: 16,
          type: "integer",
        },
        dataset_path: {
          type: "string",
        },
        device: {
          default: "auto",
          type: "string",
        },
        device_policy: {
          default: "any",
          type: "string",
        },
        epochs: {
          default: 100,
          type: "integer",
        },
        force: {
          default: false,
          type: "boolean",
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
        max_concurrent_runs: {
          default: 1,
          type: "integer",
        },
        max_disk_usage_gb: {
          anyOf: [
            {
              type: "number",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        max_runtime_seconds: {
          anyOf: [
            {
              type: "integer",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        model: {
          default: "yolov8n.pt",
          type: "string",
        },
        name: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        options: {
          anyOf: [
            {
              additionalProperties: true,
              type: "object",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        tags: {
          anyOf: [
            {
              items: {
                type: "string",
              },
              type: "array",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        task: {
          default: "detect",
          type: "string",
        },
      },
      required: ["dataset_path"],
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
  {
    name: "fovux_get_train_status",
    toolReferenceName: "fovux_train_status",
    displayName: "Training Status",
    userDescription: "Run Fovux Training Status using the local fovux-mcp server.",
    modelDescription:
      "Get current metrics and process state for an ongoing or completed YOLO training run. Use to check if training is complete or monitor loss. DO NOT use to stop training (use fovux_train_stop instead).",
    tags: ["training"],
    canBeReferencedInPrompt: true,
    mcpToolName: "train_status",
    inputSchema: {
      additionalProperties: false,
      properties: {
        run_id: {
          type: "string",
        },
      },
      required: ["run_id"],
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
  {
    name: "fovux_stop_train",
    toolReferenceName: "fovux_train_stop",
    displayName: "Stop Training",
    userDescription: "Run Fovux Stop Training using the local fovux-mcp server.",
    modelDescription:
      "Stop a running YOLO training run by its run ID. Use to abort training that is overfitting or taking too long. DO NOT use for idle or completed runs.",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    confirmationKind: "train_stop",
    mcpToolName: "train_stop",
    inputSchema: {
      additionalProperties: false,
      properties: {
        force: {
          default: false,
          type: "boolean",
        },
        run_id: {
          type: "string",
        },
      },
      required: ["run_id"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "run:start",
    policyCategory: "mutating",
  },
  {
    name: "fovux_resume_train",
    toolReferenceName: "fovux_train_resume",
    displayName: "Resume Training",
    userDescription: "Run Fovux Resume Training using the local fovux-mcp server.",
    modelDescription:
      "Resume a stopped or failed training run from its last checkpoint (weights/last.pt). Use when training was interrupted (e.g. system reboot or timeout). DO NOT use for starting a clean run (use fovux_train_start instead).",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    confirmationKind: "train_resume",
    mcpToolName: "train_resume",
    inputSchema: {
      additionalProperties: false,
      properties: {
        epochs: {
          anyOf: [
            {
              type: "integer",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        run_id: {
          type: "string",
        },
      },
      required: ["run_id"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "run:start",
    policyCategory: "mutating",
  },
  {
    name: "fovux_run_eval",
    toolReferenceName: "fovux_eval_run",
    displayName: "Run Evaluation",
    userDescription: "Run Fovux Run Evaluation using the local fovux-mcp server.",
    modelDescription:
      "Evaluate a YOLO model checkpoint against a validation dataset and return mAP metrics. Use to test performance of a trained model. DO NOT use during active training on the same run (wait until it is paused or completed).",
    tags: ["evaluation"],
    canBeReferencedInPrompt: true,
    mcpToolName: "eval_run",
    inputSchema: {
      additionalProperties: false,
      properties: {
        batch: {
          default: 16,
          type: "integer",
        },
        checkpoint: {
          type: "string",
        },
        conf: {
          default: 0.25,
          type: "number",
        },
        dataset_path: {
          type: "string",
        },
        device: {
          default: "auto",
          type: "string",
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
        iou: {
          default: 0.45,
          type: "number",
        },
        split: {
          default: "val",
          type: "string",
        },
        task: {
          default: "detect",
          type: "string",
        },
      },
      required: ["checkpoint", "dataset_path"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "run:start",
    policyCategory: "long_running",
  },
  {
    name: "fovux_compare_eval",
    toolReferenceName: "fovux_eval_compare",
    displayName: "Compare Evaluations",
    userDescription: "Run Fovux Compare Evaluations using the local fovux-mcp server.",
    modelDescription:
      "Evaluate multiple checkpoints on the same dataset side-by-side and rank them by mAP50. Use to choose the best model architecture or epoch checkpoint. DO NOT use to compare training run telemetry (use fovux_run_compare instead).",
    tags: ["evaluation"],
    canBeReferencedInPrompt: false,
    mcpToolName: "eval_compare",
    inputSchema: {
      additionalProperties: false,
      properties: {
        batch: {
          default: 16,
          type: "integer",
        },
        checkpoints: {
          items: {
            type: "string",
          },
          type: "array",
        },
        conf: {
          default: 0.25,
          type: "number",
        },
        dataset_path: {
          type: "string",
        },
        device: {
          default: "auto",
          type: "string",
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
        iou: {
          default: 0.45,
          type: "number",
        },
        split: {
          default: "val",
          type: "string",
        },
      },
      required: ["checkpoints", "dataset_path"],
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
  {
    name: "fovux_compare_run",
    toolReferenceName: "fovux_run_compare",
    displayName: "Compare Training Runs",
    userDescription: "Run Fovux Compare Training Runs using the local fovux-mcp server.",
    modelDescription:
      "Compare training runs on shared loss, metrics, and parameters, producing a markdown report and comparison charts. Use to trace training history and compare hyperparameter sets. DO NOT use to run fresh validation evaluations (use fovux_eval_compare instead).",
    tags: ["evaluation"],
    canBeReferencedInPrompt: false,
    mcpToolName: "run_compare",
    inputSchema: {
      additionalProperties: false,
      properties: {
        output_path: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        run_ids: {
          anyOf: [
            {
              items: {
                type: "string",
              },
              type: "array",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
      },
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "run:start",
    policyCategory: "mutating",
  },
  {
    name: "fovux_export_onnx",
    toolReferenceName: "fovux_export_onnx",
    displayName: "Export to ONNX",
    userDescription: "Run Fovux Export to ONNX using the local fovux-mcp server.",
    modelDescription:
      "Export a PyTorch YOLO checkpoint to ONNX format with configurable opset and parity verification. Use for cross-platform CPU/GPU inference or browser deployment. DO NOT use for mobile android deployment (use fovux_export_tflite instead).",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    confirmationKind: "export_onnx",
    mcpToolName: "export_onnx",
    inputSchema: {
      additionalProperties: false,
      properties: {
        checkpoint: {
          type: "string",
        },
        device: {
          default: "auto",
          type: "string",
        },
        dynamic: {
          default: false,
          type: "boolean",
        },
        half: {
          default: false,
          type: "boolean",
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
        opset: {
          default: 17,
          type: "integer",
        },
        output_path: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        parity_check: {
          default: true,
          type: "boolean",
        },
        parity_tolerance: {
          default: 0.001,
          type: "number",
        },
        simplify: {
          default: true,
          type: "boolean",
        },
      },
      required: ["checkpoint"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "export:write",
    policyCategory: "mutating",
  },
  {
    name: "fovux_export_tflite",
    toolReferenceName: "fovux_export_tflite",
    displayName: "Export to TFLite",
    userDescription: "Run Fovux Export to TFLite using the local fovux-mcp server.",
    modelDescription:
      "Export a YOLO checkpoint to TensorFlow Lite format. Use for mobile (Android/iOS) and Raspberry Pi edge deployments. DO NOT use for high-performance server GPU hosting (use fovux_export_onnx or TensorRT instead).",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    confirmationKind: "export_tflite",
    mcpToolName: "export_tflite",
    inputSchema: {
      additionalProperties: false,
      properties: {
        checkpoint: {
          type: "string",
        },
        device: {
          default: "auto",
          type: "string",
        },
        half: {
          default: false,
          type: "boolean",
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
        int8: {
          default: false,
          type: "boolean",
        },
        output_path: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
      },
      required: ["checkpoint"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "export:write",
    policyCategory: "mutating",
  },
  {
    name: "fovux_quantize_int8",
    toolReferenceName: "fovux_quantize_int8",
    displayName: "Quantize INT8",
    userDescription: "Run Fovux Quantize INT8 using the local fovux-mcp server.",
    modelDescription:
      "Quantize a model to INT8 precision using a calibration dataset. Use to speed up inference and shrink model sizes on CPU/edge targets. DO NOT use if you cannot provide a calibration dataset (which prevents accurate quantization).",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    confirmationKind: "quantize_int8",
    mcpToolName: "quantize_int8",
    inputSchema: {
      additionalProperties: false,
      properties: {
        calibration_dataset: {
          type: "string",
        },
        checkpoint: {
          type: "string",
        },
        device: {
          default: "auto",
          type: "string",
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
        output_path: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
      },
      required: ["checkpoint", "calibration_dataset"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "dataset:write",
    policyCategory: "mutating",
  },
  {
    name: "fovux_advise_deployment",
    toolReferenceName: "fovux_deployment_advise",
    displayName: "Deployment Advice",
    userDescription: "Run Fovux Deployment Advice using the local fovux-mcp server.",
    modelDescription:
      "Analyze deployment readiness for an exported model on a target platform profile. Checks formats, sizes, compatibility, quantization options, and generates integration code snippets. Use to guide edge deployment planning. DO NOT use for general model profiling (use fovux_model_profile instead).",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    mcpToolName: "deployment_advise",
    inputSchema: {
      additionalProperties: false,
      properties: {
        dataset_path: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
        model_path: {
          type: "string",
        },
        target_profile: {
          type: "string",
        },
      },
      required: ["model_path", "target_profile"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "export:write",
    policyCategory: "mutating",
  },
  {
    name: "fovux_profile_model",
    toolReferenceName: "fovux_model_profile",
    displayName: "Profile Model",
    userDescription: "Run Fovux Profile Model using the local fovux-mcp server.",
    modelDescription:
      "Profile a YOLO model checkpoint to measure parameters, FLOPs, layer count, memory footprint, and disk size. Use to assess if a model can fit on hardware resource budgets. DO NOT use to assess platform-specific deployment features (use fovux_deployment_advise instead).",
    tags: ["system"],
    canBeReferencedInPrompt: false,
    mcpToolName: "model_profile",
    inputSchema: {
      additionalProperties: false,
      properties: {
        checkpoint: {
          type: "string",
        },
        device: {
          default: "auto",
          type: "string",
        },
        imgsz: {
          default: 640,
          type: "integer",
        },
      },
      required: ["checkpoint"],
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
  {
    name: "fovux_delete_run",
    toolReferenceName: "fovux_run_delete",
    displayName: "Delete Run",
    userDescription: "Run Fovux Delete Run using the local fovux-mcp server.",
    modelDescription:
      "Delete a training run from registry and optionally clean up its directory in the filesystem. Use to free up disk space by deleting failed or junk runs. DO NOT use on currently running training processes unless force=True.",
    tags: ["system"],
    canBeReferencedInPrompt: false,
    confirmationKind: "run_delete",
    mcpToolName: "run_delete",
    inputSchema: {
      additionalProperties: false,
      properties: {
        delete_files: {
          default: true,
          type: "boolean",
        },
        dry_run: {
          default: false,
          type: "boolean",
        },
        force: {
          default: false,
          type: "boolean",
        },
        run_id: {
          type: "string",
        },
      },
      required: ["run_id"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "destructive",
    policyCategory: "destructive",
  },
  {
    name: "fovux_tag_run",
    toolReferenceName: "fovux_run_tag",
    displayName: "Tag Run",
    userDescription: "Run Fovux Tag Run using the local fovux-mcp server.",
    modelDescription:
      "Replace or add tags to a training run for filtering, grouping, and workspace organization. Use to mark runs as 'baseline', 'candidate', etc. DO NOT use to start or configure runs (set tags in fovux_train_start instead).",
    tags: ["system"],
    canBeReferencedInPrompt: false,
    confirmationKind: "run_tag",
    mcpToolName: "run_tag",
    inputSchema: {
      additionalProperties: false,
      properties: {
        run_id: {
          type: "string",
        },
        tags: {
          anyOf: [
            {
              items: {
                type: "string",
              },
              type: "array",
            },
            {
              type: "null",
            },
          ],
          default: null,
        },
      },
      required: ["run_id"],
      type: "object",
    },
    requiresConfirmation: true,
    requiredScope: "run:start",
    policyCategory: "mutating",
  },
  {
    name: "fovux_run_doctor",
    toolReferenceName: "fovux_doctor",
    displayName: "System Doctor",
    userDescription: "Run Fovux System Doctor using the local fovux-mcp server.",
    modelDescription:
      "Run a comprehensive diagnostic health check covering CUDA, GPU availability, disk limits, dependencies, and local Fovux server status. Use to diagnose setup issues, GPU driver failures, or connection errors. DO NOT use for training parameters or dataset inspection.",
    tags: ["system"],
    canBeReferencedInPrompt: true,
    mcpToolName: "fovux_doctor",
    inputSchema: {
      additionalProperties: false,
      properties: {},
      type: "object",
    },
    requiresConfirmation: false,
    requiredScope: "read",
    policyCategory: "read_only",
  },
] satisfies GranularToolDefinition[];
