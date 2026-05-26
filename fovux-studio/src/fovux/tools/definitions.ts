/**
 * Granular Language Model Tool definitions for fovux-studio.
 *
 * Each tool maps 1:1 to a registered fovux-mcp tool and provides
 * a typed input schema for LLM hosts.
 */

import type { GranularToolDefinition } from "./types";

export const GRANULAR_TOOLS: GranularToolDefinition[] = [
  {
    name: "fovux_dataset_inspect",
    toolReferenceName: "fovux_dataset_inspect",
    displayName: "Inspect Dataset",
    modelDescription:
      "Analyze a YOLO dataset directory and generate a quality report including class distribution, image counts, and annotation statistics.",
    tags: ["dataset"],
    canBeReferencedInPrompt: true,
    mcpToolName: "dataset_inspect",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO dataset directory containing data.yaml.",
        },
      },
      required: ["dataset_path"],
    },
  },
  {
    name: "fovux_dataset_validate",
    toolReferenceName: "fovux_dataset_validate",
    displayName: "Validate Dataset",
    modelDescription:
      "Validate a YOLO dataset for structural correctness: checks data.yaml, image-label pairing, and annotation format.",
    tags: ["dataset"],
    canBeReferencedInPrompt: false,
    mcpToolName: "dataset_validate",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO dataset directory.",
        },
      },
      required: ["dataset_path"],
    },
  },
  {
    name: "fovux_dataset_find_duplicates",
    toolReferenceName: "fovux_dataset_find_duplicates",
    displayName: "Find Dataset Duplicates",
    modelDescription:
      "Detect duplicate or near-duplicate images in a YOLO dataset using perceptual hashing.",
    tags: ["dataset"],
    canBeReferencedInPrompt: false,
    mcpToolName: "dataset_find_duplicates",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO dataset directory.",
        },
        threshold: { type: "number", description: "Hash distance threshold (default 8)." },
      },
      required: ["dataset_path"],
    },
  },
  {
    name: "fovux_train_start",
    toolReferenceName: "fovux_train_start",
    displayName: "Start Training",
    modelDescription:
      "Launch a new YOLO training run with specified dataset, model, epochs, batch size, and device.",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    mcpToolName: "train_start",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: { type: "string", description: "Path to the YOLO training dataset." },
        model: { type: "string", description: "Model architecture (e.g., yolov8n.pt)." },
        epochs: { type: "integer", description: "Number of training epochs." },
        batch: { type: "integer", description: "Batch size." },
        imgsz: { type: "integer", description: "Training image size." },
        device: { type: "string", description: "Device: auto, cpu, 0, 1, etc." },
      },
      required: ["dataset_path"],
    },
  },
  {
    name: "fovux_train_status",
    toolReferenceName: "fovux_train_status",
    displayName: "Training Status",
    modelDescription:
      "Get the current metrics and status for an ongoing or completed YOLO training run.",
    tags: ["training"],
    canBeReferencedInPrompt: true,
    mcpToolName: "train_status",
    inputSchema: {
      type: "object",
      properties: {
        run_id: { type: "string", description: "ID of the training run." },
      },
      required: ["run_id"],
    },
  },
  {
    name: "fovux_train_stop",
    toolReferenceName: "fovux_train_stop",
    displayName: "Stop Training",
    modelDescription: "Stop a running YOLO training run by its run ID.",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    mcpToolName: "train_stop",
    inputSchema: {
      type: "object",
      properties: {
        run_id: { type: "string", description: "ID of the training run to stop." },
      },
      required: ["run_id"],
    },
  },
  {
    name: "fovux_eval_run",
    toolReferenceName: "fovux_eval_run",
    displayName: "Run Evaluation",
    modelDescription:
      "Evaluate a YOLO model checkpoint against a validation dataset and return mAP metrics.",
    tags: ["evaluation"],
    canBeReferencedInPrompt: true,
    mcpToolName: "eval_run",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: { type: "string", description: "Model checkpoint path or name." },
        dataset_path: { type: "string", description: "Validation dataset path." },
      },
      required: ["checkpoint", "dataset_path"],
    },
  },
  {
    name: "fovux_eval_compare",
    toolReferenceName: "fovux_eval_compare",
    displayName: "Compare Evaluations",
    modelDescription: "Compare metrics between two training runs side by side.",
    tags: ["evaluation"],
    canBeReferencedInPrompt: false,
    mcpToolName: "eval_compare",
    inputSchema: {
      type: "object",
      properties: {
        run_id_a: { type: "string", description: "First run ID." },
        run_id_b: { type: "string", description: "Second run ID." },
      },
      required: ["run_id_a", "run_id_b"],
    },
  },
  {
    name: "fovux_export_onnx",
    toolReferenceName: "fovux_export_onnx",
    displayName: "Export to ONNX",
    modelDescription:
      "Export a PyTorch YOLO checkpoint to ONNX format with configurable opset and input shapes.",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    mcpToolName: "export_onnx",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: { type: "string", description: "Model checkpoint to export." },
        imgsz: { type: "integer", description: "Export image size." },
      },
      required: ["checkpoint"],
    },
  },
  {
    name: "fovux_export_tflite",
    toolReferenceName: "fovux_export_tflite",
    displayName: "Export to TFLite",
    modelDescription:
      "Export a YOLO checkpoint to TensorFlow Lite format for mobile and edge deployment.",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    mcpToolName: "export_tflite",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: { type: "string", description: "Model checkpoint to export." },
        imgsz: { type: "integer", description: "Export image size." },
      },
      required: ["checkpoint"],
    },
  },
  {
    name: "fovux_quantize_int8",
    toolReferenceName: "fovux_quantize_int8",
    displayName: "Quantize INT8",
    modelDescription:
      "Quantize a model to INT8 precision using a calibration dataset for edge deployment.",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    mcpToolName: "quantize_int8",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: { type: "string", description: "Model checkpoint to quantize." },
        calibration_dataset: {
          type: "string",
          description: "Path to calibration dataset.",
        },
      },
      required: ["checkpoint", "calibration_dataset"],
    },
  },
  {
    name: "fovux_doctor",
    toolReferenceName: "fovux_doctor",
    displayName: "System Doctor",
    modelDescription:
      "Run a diagnostic health check covering CUDA, disk, CPU, RAM, dependencies, and active training runs.",
    tags: ["system"],
    canBeReferencedInPrompt: true,
    mcpToolName: "fovux_doctor",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];
