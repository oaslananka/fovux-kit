/**
 * Granular Language Model Tool definitions for fovux-studio.
 *
 * Each tool maps 1:1 to a registered fovux-mcp tool and provides
 * a typed input schema for LLM hosts with constraints, enums, and examples.
 */

import type { GranularToolDefinition } from "./types";

export const GRANULAR_TOOLS: GranularToolDefinition[] = [
  {
    name: "fovux_dataset_inspect",
    toolReferenceName: "fovux_dataset_inspect",
    displayName: "Inspect Dataset",
    modelDescription:
      "Produce comprehensive statistics and quality metrics for a dataset. Use when you need to check class balance, Gini index, image sizes, or get an auto-fix recommendation plan. DO NOT use for deep structural checks (use fovux_dataset_validate instead) or perceptual duplicate search (use fovux_dataset_find_duplicates).",
    tags: ["dataset"],
    canBeReferencedInPrompt: true,
    mcpToolName: "dataset_inspect",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO dataset directory containing data.yaml.",
          examples: ["C:/Users/Admin/datasets/my_dataset", "./data/coco128"],
        },
        format: {
          type: "string",
          description: "Dataset format to analyze.",
          enum: ["auto", "yolo", "coco"],
          default: "auto",
        },
        include_samples: {
          type: "boolean",
          description: "Whether to include sample image paths in the output report.",
          default: true,
        },
        max_images_analyzed: {
          type: "integer",
          description: "Cap on the number of images to read to prevent timeouts.",
          minimum: 1,
          maximum: 100000,
          default: 10000,
          examples: [1000, 5000, 10000],
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
      "Validate a YOLO/COCO dataset for structural correctness. Checks data.yaml, image-label pairing, and annotation format. Use to ensure the dataset is ready for training. DO NOT use if you only want descriptive statistics (use fovux_dataset_inspect instead).",
    tags: ["dataset"],
    canBeReferencedInPrompt: false,
    mcpToolName: "dataset_validate",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO dataset directory.",
          examples: ["C:/Users/Admin/datasets/traffic_signs"],
        },
        format: {
          type: "string",
          description: "Dataset format.",
          enum: ["auto", "yolo", "coco"],
          default: "auto",
        },
        check_image_readable: {
          type: "boolean",
          description: "Verify that all image files can be loaded by PIL without corruption.",
          default: true,
        },
        check_bbox_bounds: {
          type: "boolean",
          description: "Ensure bbox coordinates lie strictly within [0.0, 1.0].",
          default: true,
        },
        check_class_id_range: {
          type: "boolean",
          description:
            "Ensure annotated class IDs match the categories defined in dataset metadata.",
          default: true,
        },
        strict: {
          type: "boolean",
          description: "Fail on warnings as well as critical errors.",
          default: false,
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
      "Detect duplicate or near-duplicate images in a YOLO dataset using perceptual hashing. Use to clean redundant training data and resolve split leakage. DO NOT use for general file comparison or structural validation.",
    tags: ["dataset"],
    canBeReferencedInPrompt: false,
    mcpToolName: "dataset_find_duplicates",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO dataset directory.",
          examples: ["C:/Users/Admin/datasets/my_dataset"],
        },
        algorithm: {
          type: "string",
          description: "Perceptual hashing algorithm to use.",
          enum: ["phash", "dhash", "whash", "average"],
          default: "phash",
        },
        hamming_threshold: {
          type: "integer",
          description:
            "Maximum hamming distance (0-64) for near-duplicates. Lower values mean stricter matching.",
          minimum: 0,
          maximum: 64,
          default: 5,
          examples: [3, 5, 8],
        },
        across_splits: {
          type: "boolean",
          description: "Detect duplicate images leaked between train, val, or test splits.",
          default: true,
        },
      },
      required: ["dataset_path"],
    },
  },
  {
    name: "fovux_annotation_quality_check",
    toolReferenceName: "fovux_annotation_quality_check",
    displayName: "Annotation Quality Check",
    modelDescription:
      "Run targeted heuristic checks for common bounding box anomalies (out of bounds, extremely tiny, highly overlapping, empty). Use to clean up annotation quality before training. DO NOT use for general dataset structure (use fovux_dataset_validate).",
    tags: ["dataset"],
    canBeReferencedInPrompt: false,
    mcpToolName: "annotation_quality_check",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO/COCO dataset directory.",
          examples: ["C:/Users/Admin/datasets/traffic_signs"],
        },
        checks: {
          type: "array",
          items: {
            type: "string",
            enum: ["tiny_box", "out_of_bounds", "overlapping", "empty_label"],
          },
          description: "Specific checks to run. If empty, runs all checks.",
        },
      },
      required: ["dataset_path"],
    },
  },
  {
    name: "fovux_train_start",
    toolReferenceName: "fovux_train_start",
    displayName: "Start Training",
    modelDescription:
      "Launch a new YOLO training run as a non-blocking background subprocess. Use this to start training after preflight/validation checks are successful. DO NOT use if there is an active training run unless force=True or max_concurrent_runs is increased.",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    mcpToolName: "train_start",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO training dataset.",
          examples: ["C:/Users/Admin/datasets/my_dataset"],
        },
        model: {
          type: "string",
          description: "Model architecture file or checkpoint to start from.",
          default: "yolov8n.pt",
          examples: ["yolov8n.pt", "yolov8s.yaml"],
        },
        epochs: {
          type: "integer",
          description: "Number of training epochs.",
          minimum: 1,
          default: 100,
          examples: [50, 100, 200],
        },
        batch: {
          type: "integer",
          description: "Batch size (images per step).",
          minimum: 1,
          default: 16,
          examples: [8, 16, 32],
        },
        imgsz: {
          type: "integer",
          description: "Training image dimension.",
          minimum: 32,
          default: 640,
          examples: [320, 640, 1280],
        },
        device: {
          type: "string",
          description: "Compute device to run training on (auto, cpu, cuda GPU index).",
          default: "auto",
          examples: ["auto", "cpu", "cuda:0", "0"],
        },
        task: {
          type: "string",
          description: "YOLO training task type.",
          enum: ["detect", "segment", "classify", "pose", "obb"],
          default: "detect",
        },
        name: {
          type: "string",
          description: "Explicit run identifier. If omitted, a random ID is generated.",
          examples: ["yolov8_traffic_01"],
        },
        force: {
          type: "boolean",
          description: "Overwrite existing run directory if it exists with the same name.",
          default: false,
        },
        max_concurrent_runs: {
          type: "integer",
          description: "Limit on concurrent active runs. Restricts resource exhaustion.",
          minimum: 1,
          default: 1,
        },
        tags: {
          type: "array",
          items: { type: "string" },
          description: "Tags for classifying the run.",
          examples: [["baseline", "detect"]],
        },
        max_runtime_seconds: {
          type: "integer",
          description: "Hard time budget in seconds before automatic run termination.",
          minimum: 1,
        },
        max_disk_usage_gb: {
          type: "number",
          description: "Hard disk budget in gigabytes for saved checkpoints.",
          minimum: 0.1,
        },
        device_policy: {
          type: "string",
          description: "Enforces specific device requirements.",
          enum: ["any", "gpu_only", "cpu_only"],
          default: "any",
        },
      },
      required: ["dataset_path"],
    },
  },
  {
    name: "fovux_train_preflight",
    toolReferenceName: "fovux_train_preflight",
    displayName: "Training Preflight Check",
    modelDescription:
      "Run safety and diagnostic preflight checks before launching training. Checks dataset validity, model source, device availability, disk budgets, and run directory collisions. Use to prevent runtime training failures. DO NOT use to launch training (use fovux_train_start instead).",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    mcpToolName: "train_preflight",
    inputSchema: {
      type: "object",
      properties: {
        dataset_path: {
          type: "string",
          description: "Path to the YOLO training dataset.",
          examples: ["C:/Users/Admin/datasets/my_dataset"],
        },
        model: {
          type: "string",
          description: "Model architecture or checkpoint.",
          default: "yolov8n.pt",
        },
        epochs: {
          type: "integer",
          description: "Number of epochs planned.",
          minimum: 1,
          default: 100,
        },
        batch: {
          type: "integer",
          description: "Batch size planned.",
          minimum: 1,
          default: 16,
        },
        imgsz: {
          type: "integer",
          description: "Image size planned.",
          minimum: 32,
          default: 640,
        },
        device: {
          type: "string",
          description: "Target compute device.",
          default: "auto",
        },
        task: {
          type: "string",
          description: "Task type.",
          enum: ["detect", "segment", "classify", "pose", "obb"],
          default: "detect",
        },
        name: {
          type: "string",
          description: "Planned run ID.",
        },
      },
      required: ["dataset_path"],
    },
  },
  {
    name: "fovux_train_status",
    toolReferenceName: "fovux_train_status",
    displayName: "Training Status",
    modelDescription:
      "Get current metrics and process state for an ongoing or completed YOLO training run. Use to check if training is complete or monitor loss. DO NOT use to stop training (use fovux_train_stop instead).",
    tags: ["training"],
    canBeReferencedInPrompt: true,
    mcpToolName: "train_status",
    inputSchema: {
      type: "object",
      properties: {
        run_id: {
          type: "string",
          description: "ID of the training run to check.",
          examples: ["run_demo", "yolov8_traffic_01"],
        },
      },
      required: ["run_id"],
    },
  },
  {
    name: "fovux_train_stop",
    toolReferenceName: "fovux_train_stop",
    displayName: "Stop Training",
    modelDescription:
      "Stop a running YOLO training run by its run ID. Use to abort training that is overfitting or taking too long. DO NOT use for idle or completed runs.",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    mcpToolName: "train_stop",
    inputSchema: {
      type: "object",
      properties: {
        run_id: {
          type: "string",
          description: "ID of the training run to stop.",
          examples: ["yolov8_traffic_01"],
        },
        force: {
          type: "boolean",
          description: "Force kill the process group immediately using SIGKILL if it hangs.",
          default: false,
        },
      },
      required: ["run_id"],
    },
  },
  {
    name: "fovux_train_resume",
    toolReferenceName: "fovux_train_resume",
    displayName: "Resume Training",
    modelDescription:
      "Resume a stopped or failed training run from its last checkpoint (weights/last.pt). Use when training was interrupted (e.g. system reboot or timeout). DO NOT use for starting a clean run (use fovux_train_start instead).",
    tags: ["training"],
    canBeReferencedInPrompt: false,
    mcpToolName: "train_resume",
    inputSchema: {
      type: "object",
      properties: {
        run_id: {
          type: "string",
          description: "ID of the training run to resume.",
          examples: ["yolov8_traffic_01"],
        },
        epochs: {
          type: "integer",
          description: "Optionally adjust the total number of epochs for the resumed training run.",
          minimum: 1,
        },
      },
      required: ["run_id"],
    },
  },
  {
    name: "fovux_eval_run",
    toolReferenceName: "fovux_eval_run",
    displayName: "Run Evaluation",
    modelDescription:
      "Evaluate a YOLO model checkpoint against a validation dataset and return mAP metrics. Use to test performance of a trained model. DO NOT use during active training on the same run (wait until it is paused or completed).",
    tags: ["evaluation"],
    canBeReferencedInPrompt: true,
    mcpToolName: "eval_run",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: {
          type: "string",
          description: "Model checkpoint path (absolute or relative to FOVUX_HOME/models).",
          examples: ["C:/Users/Admin/.fovux/runs/yolov8_traffic_01/weights/best.pt", "best.pt"],
        },
        dataset_path: {
          type: "string",
          description: "Validation/test dataset path.",
          examples: ["C:/Users/Admin/datasets/my_dataset"],
        },
        split: {
          type: "string",
          description: "Dataset split to evaluate on.",
          enum: ["val", "test", "train"],
          default: "val",
        },
        batch: {
          type: "integer",
          description: "Inference batch size.",
          minimum: 1,
          default: 16,
        },
        imgsz: {
          type: "integer",
          description: "Inference image dimension.",
          minimum: 32,
          default: 640,
        },
        device: {
          type: "string",
          description: "Target compute device.",
          default: "auto",
        },
        conf: {
          type: "number",
          description: "Confidence threshold for detections.",
          minimum: 0.0,
          maximum: 1.0,
          default: 0.25,
        },
        iou: {
          type: "number",
          description: "NMS IoU threshold.",
          minimum: 0.0,
          maximum: 1.0,
          default: 0.45,
        },
        task: {
          type: "string",
          description: "YOLO task type.",
          enum: ["detect", "segment", "classify", "pose", "obb"],
          default: "detect",
        },
      },
      required: ["checkpoint", "dataset_path"],
    },
  },
  {
    name: "fovux_eval_compare",
    toolReferenceName: "fovux_eval_compare",
    displayName: "Compare Evaluations",
    modelDescription:
      "Evaluate multiple checkpoints on the same dataset side-by-side and rank them by mAP50. Use to choose the best model architecture or epoch checkpoint. DO NOT use to compare training run telemetry (use fovux_run_compare instead).",
    tags: ["evaluation"],
    canBeReferencedInPrompt: false,
    mcpToolName: "eval_compare",
    inputSchema: {
      type: "object",
      properties: {
        checkpoints: {
          type: "array",
          items: { type: "string" },
          description: "List of model checkpoints to evaluate.",
          examples: [["run1/weights/best.pt", "run2/weights/best.pt"]],
        },
        dataset_path: {
          type: "string",
          description: "Evaluation dataset path.",
          examples: ["C:/Users/Admin/datasets/my_dataset"],
        },
        split: {
          type: "string",
          description: "Dataset split to evaluate on.",
          enum: ["val", "test"],
          default: "val",
        },
        batch: {
          type: "integer",
          description: "Batch size.",
          minimum: 1,
          default: 16,
        },
        imgsz: {
          type: "integer",
          description: "Image size.",
          minimum: 32,
          default: 640,
        },
        device: {
          type: "string",
          description: "Target compute device.",
          default: "auto",
        },
        conf: {
          type: "number",
          description: "Confidence threshold.",
          minimum: 0.0,
          maximum: 1.0,
          default: 0.25,
        },
        iou: {
          type: "number",
          description: "NMS IoU threshold.",
          minimum: 0.0,
          maximum: 1.0,
          default: 0.45,
        },
      },
      required: ["checkpoints", "dataset_path"],
    },
  },
  {
    name: "fovux_run_compare",
    toolReferenceName: "fovux_run_compare",
    displayName: "Compare Training Runs",
    modelDescription:
      "Compare training runs on shared loss, metrics, and parameters, producing a markdown report and comparison charts. Use to trace training history and compare hyperparameter sets. DO NOT use to run fresh validation evaluations (use fovux_eval_compare instead).",
    tags: ["evaluation"],
    canBeReferencedInPrompt: false,
    mcpToolName: "run_compare",
    inputSchema: {
      type: "object",
      properties: {
        run_ids: {
          type: "array",
          items: { type: "string" },
          description: "List of run IDs to compare. If empty, all non-archived runs are compared.",
          examples: [["yolov8_traffic_01", "yolov8_traffic_02"]],
        },
        output_path: {
          type: "string",
          description: "Optional output markdown filepath to write the report to.",
        },
      },
    },
  },
  {
    name: "fovux_export_onnx",
    toolReferenceName: "fovux_export_onnx",
    displayName: "Export to ONNX",
    modelDescription:
      "Export a PyTorch YOLO checkpoint to ONNX format with configurable opset and parity verification. Use for cross-platform CPU/GPU inference or browser deployment. DO NOT use for mobile android deployment (use fovux_export_tflite instead).",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    mcpToolName: "export_onnx",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: {
          type: "string",
          description: "Model checkpoint filepath to export.",
          examples: ["best.pt"],
        },
        output_path: {
          type: "string",
          description: "Optional custom output path for the ONNX file.",
        },
        imgsz: {
          type: "integer",
          description: "Export image dimension.",
          minimum: 32,
          default: 640,
        },
        opset: {
          type: "integer",
          description: "ONNX opset version.",
          minimum: 7,
          maximum: 20,
          default: 17,
        },
        dynamic: {
          type: "boolean",
          description: "Support dynamic input dimensions.",
          default: false,
        },
        simplify: {
          type: "boolean",
          description: "Optimize ONNX graph structures via onnxsimplifier.",
          default: true,
        },
        half: {
          type: "boolean",
          description: "Use FP16 half precision.",
          default: false,
        },
        nms: {
          type: "boolean",
          description: "Embed CoreML/ONNX Non-Maximum Suppression directly inside the model graph.",
          default: false,
        },
      },
      required: ["checkpoint"],
    },
  },
  {
    name: "fovux_export_tflite",
    toolReferenceName: "fovux_export_tflite",
    displayName: "Export to TFLite",
    modelDescription:
      "Export a YOLO checkpoint to TensorFlow Lite format. Use for mobile (Android/iOS) and Raspberry Pi edge deployments. DO NOT use for high-performance server GPU hosting (use fovux_export_onnx or TensorRT instead).",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    mcpToolName: "export_tflite",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: {
          type: "string",
          description: "Model checkpoint to export.",
          examples: ["best.pt"],
        },
        output_path: {
          type: "string",
          description: "Optional custom output path for the .tflite file.",
        },
        imgsz: {
          type: "integer",
          description: "Export image dimension.",
          minimum: 32,
          default: 640,
        },
        half: {
          type: "boolean",
          description: "Use FP16 float precision.",
          default: false,
        },
        int8: {
          type: "boolean",
          description:
            "Convert model weights to INT8 integer values (requires calibration dataset).",
          default: false,
        },
      },
      required: ["checkpoint"],
    },
  },
  {
    name: "fovux_quantize_int8",
    toolReferenceName: "fovux_quantize_int8",
    displayName: "Quantize INT8",
    modelDescription:
      "Quantize a model to INT8 precision using a calibration dataset. Use to speed up inference and shrink model sizes on CPU/edge targets. DO NOT use if you cannot provide a calibration dataset (which prevents accurate quantization).",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    mcpToolName: "quantize_int8",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: {
          type: "string",
          description: "Model checkpoint to quantize.",
          examples: ["best.pt"],
        },
        calibration_dataset: {
          type: "string",
          description: "Path to a representative calibration dataset directory.",
          examples: ["C:/Users/Admin/datasets/my_dataset"],
        },
        output_path: {
          type: "string",
          description: "Optional custom output path for the quantized model.",
        },
        imgsz: {
          type: "integer",
          description: "Quantization input dimension.",
          minimum: 32,
          default: 640,
        },
      },
      required: ["checkpoint", "calibration_dataset"],
    },
  },
  {
    name: "fovux_deployment_advise",
    toolReferenceName: "fovux_deployment_advise",
    displayName: "Deployment Advice",
    modelDescription:
      "Analyze deployment readiness for an exported model on a target platform profile. Checks formats, sizes, compatibility, quantization options, and generates integration code snippets. Use to guide edge deployment planning. DO NOT use for general model profiling (use fovux_model_profile instead).",
    tags: ["export"],
    canBeReferencedInPrompt: false,
    mcpToolName: "deployment_advise",
    inputSchema: {
      type: "object",
      properties: {
        model_path: {
          type: "string",
          description: "Path to the exported model file (.onnx, .tflite, .engine).",
          examples: ["best.onnx"],
        },
        target_profile: {
          type: "string",
          description: "Target deployment hardware profile.",
          enum: [
            "cpu_server",
            "nvidia_gpu_tensorrt",
            "jetson",
            "raspberry_pi",
            "android_tflite",
            "browser_wasm",
          ],
          examples: ["android_tflite", "raspberry_pi"],
        },
        dataset_path: {
          type: "string",
          description: "Optional validation dataset to run accuracy and parity benchmarks.",
        },
        imgsz: {
          type: "integer",
          description: "Benchmark input image size.",
          minimum: 32,
          default: 640,
        },
      },
      required: ["model_path", "target_profile"],
    },
  },
  {
    name: "fovux_model_profile",
    toolReferenceName: "fovux_model_profile",
    displayName: "Profile Model",
    modelDescription:
      "Profile a YOLO model checkpoint to measure parameters, FLOPs, layer count, memory footprint, and disk size. Use to assess if a model can fit on hardware resource budgets. DO NOT use to assess platform-specific deployment features (use fovux_deployment_advise instead).",
    tags: ["system"],
    canBeReferencedInPrompt: false,
    mcpToolName: "model_profile",
    inputSchema: {
      type: "object",
      properties: {
        checkpoint: {
          type: "string",
          description: "Model checkpoint path to profile.",
          examples: ["best.pt"],
        },
        imgsz: {
          type: "integer",
          description: "Inference dimension to calculate GFLOPs.",
          minimum: 32,
          default: 640,
        },
        device: {
          type: "string",
          description: "Device to run profiling benchmarks on.",
          default: "auto",
        },
      },
      required: ["checkpoint"],
    },
  },
  {
    name: "fovux_run_delete",
    toolReferenceName: "fovux_run_delete",
    displayName: "Delete Run",
    modelDescription:
      "Delete a training run from registry and optionally clean up its directory in the filesystem. Use to free up disk space by deleting failed or junk runs. DO NOT use on currently running training processes unless force=True.",
    tags: ["system"],
    canBeReferencedInPrompt: false,
    mcpToolName: "run_delete",
    inputSchema: {
      type: "object",
      properties: {
        run_id: {
          type: "string",
          description: "ID of the training run to delete.",
          examples: ["yolov8_traffic_01"],
        },
        delete_files: {
          type: "boolean",
          description: "Whether to delete the run directory and all saved weights from disk.",
          default: true,
        },
        force: {
          type: "boolean",
          description: "Terminate the run first if it is currently active, then delete.",
          default: false,
        },
        dry_run: {
          type: "boolean",
          description: "Calculate what files would be deleted without actually removing them.",
          default: false,
        },
      },
      required: ["run_id"],
    },
  },
  {
    name: "fovux_run_tag",
    toolReferenceName: "fovux_run_tag",
    displayName: "Tag Run",
    modelDescription:
      "Replace or add tags to a training run for filtering, grouping, and workspace organization. Use to mark runs as 'baseline', 'candidate', etc. DO NOT use to start or configure runs (set tags in fovux_train_start instead).",
    tags: ["system"],
    canBeReferencedInPrompt: false,
    mcpToolName: "run_tag",
    inputSchema: {
      type: "object",
      properties: {
        run_id: {
          type: "string",
          description: "ID of the training run to tag.",
          examples: ["yolov8_traffic_01"],
        },
        tags: {
          type: "array",
          items: { type: "string" },
          description: "Complete list of new tags for the run.",
          examples: [["baseline", "v1.0"]],
        },
      },
      required: ["run_id"],
    },
  },
  {
    name: "fovux_doctor",
    toolReferenceName: "fovux_doctor",
    displayName: "System Doctor",
    modelDescription:
      "Run a comprehensive diagnostic health check covering CUDA, GPU availability, disk limits, dependencies, and local Fovux server status. Use to diagnose setup issues, GPU driver failures, or connection errors. DO NOT use for training parameters or dataset inspection.",
    tags: ["system"],
    canBeReferencedInPrompt: true,
    mcpToolName: "fovux_doctor",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];
