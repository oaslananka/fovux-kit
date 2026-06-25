/* eslint-disable @typescript-eslint/no-explicit-any */
import * as vscode from "vscode";

import { EmbeddedMcpClient } from "./mcpClient";
import { GRANULAR_TOOLS } from "./tools/definitions";

interface FovuxToolInvocationInput {
  tool: string;
  args?: Record<string, unknown>;
}

interface GranularToolInput {
  [key: string]: unknown;
}

export function registerFovuxLanguageModelTool(context: vscode.ExtensionContext): void {
  if (!vscode.lm?.registerTool) {
    return;
  }

  // Register the generic dispatcher (backward compatible)
  const genericTool: vscode.LanguageModelTool<FovuxToolInvocationInput> = {
    prepareInvocation(_options) {
      const toolName = _options.input.tool;
      const args = _options.input.args ?? {};
      const confirmation = getConfirmationMessage(toolName, args);

      return {
        invocationMessage: `Running Fovux tool ${toolName}`,
        confirmationMessages: {
          title: confirmation ? `Run Fovux Tool: ${toolName}?` : "Run Fovux MCP tool?",
          message:
            confirmation || `Fovux Studio will call ${toolName} on your local fovux-mcp server.`,
        },
      };
    },
    async invoke(_options) {
      try {
        const result = await new EmbeddedMcpClient().callTool<any>(
          _options.input.tool,
          _options.input.args ?? {}
        );
        const summary = formatToolOutputSummary(_options.input.tool, result);
        const parts = [];
        if (summary) {
          parts.push(new vscode.LanguageModelTextPart(summary));
        }
        parts.push(new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)));
        return new vscode.LanguageModelToolResult(parts);
      } catch (error) {
        throw new Error(formatActionableToolError(_options.input.tool, error));
      }
    },
  };

  context.subscriptions.push(vscode.lm.registerTool("fovux_call_tool", genericTool));

  // Register granular tools
  for (const definition of GRANULAR_TOOLS) {
    const granularTool: vscode.LanguageModelTool<GranularToolInput> = {
      prepareInvocation(_options) {
        const confirmation = getConfirmationMessage(definition.mcpToolName, _options.input);
        return {
          invocationMessage: `Running ${definition.displayName}`,
          confirmationMessages: {
            title: `Run ${definition.displayName}?`,
            message:
              confirmation ||
              `Fovux Studio will call ${definition.mcpToolName} on your local fovux-mcp server.`,
          },
        };
      },
      async invoke(options) {
        try {
          const client = new EmbeddedMcpClient();
          const result = await client.callTool<any>(definition.mcpToolName, options.input);
          const summary = formatToolOutputSummary(definition.mcpToolName, result);
          const parts = [];
          if (summary) {
            parts.push(new vscode.LanguageModelTextPart(summary));
          }
          parts.push(new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)));
          return new vscode.LanguageModelToolResult(parts);
        } catch (error) {
          throw new Error(formatActionableToolError(definition.mcpToolName, error));
        }
      },
    };

    context.subscriptions.push(vscode.lm.registerTool(definition.name, granularTool));
  }
}

function getConfirmationMessage(
  mcpToolName: string,
  input: Record<string, any>
): vscode.MarkdownString | undefined {
  if (
    ![
      "train_start",
      "train_stop",
      "train_resume",
      "export_onnx",
      "export_tflite",
      "quantize_int8",
      "run_delete",
      "run_tag",
    ].includes(mcpToolName)
  ) {
    return undefined;
  }

  const markdown = new vscode.MarkdownString();
  markdown.isTrusted = true;

  switch (mcpToolName) {
    case "train_start": {
      markdown.appendMarkdown(`### 🚀 Fovux: Start Training Run\n`);
      markdown.appendMarkdown(
        `You are about to launch a new YOLO training run on your local machine.\n\n`
      );
      markdown.appendMarkdown(`**Configuration Summary:**\n\n`);
      markdown.appendMarkdown(`- **Dataset Path:** \`${input.dataset_path}\`\n`);
      markdown.appendMarkdown(`- **Model:** \`${input.model || "yolov8n.pt"}\`\n`);
      markdown.appendMarkdown(
        `- **Epochs:** \`${input.epochs !== undefined ? input.epochs : 100}\`\n`
      );
      markdown.appendMarkdown(
        `- **Batch Size:** \`${input.batch !== undefined ? input.batch : 16}\`\n`
      );
      markdown.appendMarkdown(
        `- **Image Size:** \`${input.imgsz !== undefined ? input.imgsz : 640}\`\n`
      );
      markdown.appendMarkdown(`- **Device:** \`${input.device || "auto"}\`\n`);
      if (input.device_policy) {
        markdown.appendMarkdown(`- **Device Policy:** \`${input.device_policy}\`\n`);
      }
      markdown.appendMarkdown(
        `\n> ⚠️ **Warning:** Training is highly resource-intensive and may cause high CPU/GPU load.`
      );
      break;
    }
    case "train_stop": {
      markdown.appendMarkdown(`### 🛑 Fovux: Stop Training Run\n`);
      markdown.appendMarkdown(
        `Are you sure you want to stop the training run **${input.run_id}**?\n\n`
      );
      markdown.appendMarkdown(`This will immediately terminate the background subprocess.`);
      break;
    }
    case "train_resume": {
      markdown.appendMarkdown(`### ⏯️ Fovux: Resume Training Run\n`);
      markdown.appendMarkdown(
        `Are you sure you want to resume the training run **${input.run_id}**?\n\n`
      );
      markdown.appendMarkdown(
        `It will resume training from its last checkpoint (\`weights/last.pt\`).\n`
      );
      if (input.epochs !== undefined) {
        markdown.appendMarkdown(`- **Adjusted Epochs:** \`${input.epochs}\`\n`);
      }
      break;
    }
    case "export_onnx": {
      markdown.appendMarkdown(`### 📦 Fovux: Export to ONNX\n`);
      markdown.appendMarkdown(
        `Export model checkpoint \`${input.checkpoint}\` to ONNX format?\n\n`
      );
      if (input.imgsz !== undefined) {
        markdown.appendMarkdown(`- **Image Size:** \`${input.imgsz}\`\n`);
      }
      if (input.opset !== undefined) {
        markdown.appendMarkdown(`- **ONNX Opset:** \`${input.opset}\`\n`);
      }
      break;
    }
    case "export_tflite": {
      markdown.appendMarkdown(`### 📦 Fovux: Export to TFLite\n`);
      markdown.appendMarkdown(
        `Export model checkpoint \`${input.checkpoint}\` to TensorFlow Lite format?\n\n`
      );
      if (input.imgsz !== undefined) {
        markdown.appendMarkdown(`- **Image Size:** \`${input.imgsz}\`\n`);
      }
      if (input.int8) {
        markdown.appendMarkdown(`- **INT8 Quantization:** Enabled\n`);
      }
      break;
    }
    case "quantize_int8": {
      markdown.appendMarkdown(`### ⚡ Fovux: Quantize INT8\n`);
      markdown.appendMarkdown(
        `Quantize model checkpoint \`${input.checkpoint}\` to INT8 precision?\n\n`
      );
      markdown.appendMarkdown(`- **Calibration Dataset:** \`${input.calibration_dataset}\`\n`);
      if (input.imgsz !== undefined) {
        markdown.appendMarkdown(`- **Image Size:** \`${input.imgsz}\`\n`);
      }
      break;
    }
    case "run_delete": {
      markdown.appendMarkdown(`### 🗑️ Fovux: Delete Training Run\n`);
      markdown.appendMarkdown(`Are you sure you want to delete the run **${input.run_id}**?\n\n`);
      if (input.delete_files !== false) {
        markdown.appendMarkdown(
          `> 🔴 **Caution:** This will permanently delete the run directory and all saved checkpoints from disk!`
        );
      } else {
        markdown.appendMarkdown(
          `This will remove the run from the registry database but keep the files on disk.`
        );
      }
      break;
    }
    case "run_tag": {
      markdown.appendMarkdown(`### 🏷️ Fovux: Tag Training Run\n`);
      markdown.appendMarkdown(`Update tags on training run **${input.run_id}**?\n\n`);
      if (input.tags) {
        markdown.appendMarkdown(`- **New Tags:** \`${JSON.stringify(input.tags)}\`\n`);
      }
      break;
    }
  }

  return markdown;
}

function formatActionableToolError(mcpToolName: string, error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  const redacted = raw
    .replace(/Bearer\s+[A-Za-z0-9._~+\/=:-]+/gi, "Bearer [REDACTED]")
    .replace(/[A-Za-z]:\\[^\s`"]+/g, "[LOCAL_PATH]")
    .replace(/\/[^\s`"]{2,}(?:\/[^\s`"]+)*/g, "[LOCAL_PATH]");
  return [
    `Fovux tool ${mcpToolName} failed.`,
    `Reason: ${redacted.slice(0, 800)}`,
    "Next steps: verify the fovux-mcp server is running, check required paths in Fovux Studio, and retry with corrected arguments. Do not expose bearer tokens or full private paths in chat.",
  ].join("\n");
}

function formatToolOutputSummary(mcpToolName: string, result: any): string | undefined {
  if (!result || typeof result !== "object") {
    return undefined;
  }

  const lines: string[] = [];

  switch (mcpToolName) {
    case "dataset_inspect": {
      if (result.dataset_card) {
        return `## Inspect Dataset Summary\n\n${result.dataset_card}\n\n---\n`;
      }
      lines.push(`## Inspect Dataset Summary`);
      lines.push(`- **Format Detected:** ${result.format_detected}`);
      lines.push(`- **Total Images:** ${result.total_images}`);
      lines.push(`- **Total Annotations:** ${result.total_annotations}`);
      lines.push(`- **Quality Score:** ${result.quality_score}/100`);
      break;
    }
    case "dataset_validate": {
      lines.push(`## Dataset Validation Result`);
      lines.push(`- **Format:** ${result.format_detected}`);
      lines.push(`- **Status:** ${result.errors_count === 0 ? "✅ Passed" : "❌ Failed"}`);
      lines.push(`- **Errors:** ${result.errors_count}`);
      lines.push(`- **Warnings:** ${result.warnings_count}`);
      break;
    }
    case "dataset_find_duplicates": {
      lines.push(`## Perceptual Duplicate Search`);
      lines.push(`- **Duplicates Found:** ${result.total_duplicates_found}`);
      lines.push(`- **Groups:** ${result.duplicate_groups_count}`);
      break;
    }
    case "train_start": {
      lines.push(`## Training Started Successfully`);
      lines.push(`- **Run ID:** ${result.run_id}`);
      lines.push(`- **Status:** ${result.status}`);
      lines.push(`- **PID:** ${result.pid}`);
      lines.push(`- **Output Path:** ${result.run_path}`);
      break;
    }
    case "train_status": {
      lines.push(`## Training Status Update`);
      lines.push(`- **Run ID:** ${result.run_id}`);
      lines.push(`- **Status:** ${result.status}`);
      lines.push(`- **Epoch:** ${result.current_epoch}`);
      lines.push(`- **Best mAP50:** ${result.best_map50}`);
      break;
    }
    case "eval_run": {
      lines.push(`## Evaluation Metrics`);
      lines.push(`- **mAP50:** ${result.map50}`);
      lines.push(`- **mAP50-95:** ${result.map50_95}`);
      lines.push(`- **Precision:** ${result.precision}`);
      lines.push(`- **Recall:** ${result.recall}`);
      break;
    }
    case "export_onnx": {
      lines.push(`## ONNX Export Complete`);
      lines.push(`- **ONNX Path:** ${result.onnx_path}`);
      lines.push(`- **File Size:** ${result.file_size_mb} MB`);
      break;
    }
    case "export_tflite": {
      lines.push(`## TFLite Export Complete`);
      lines.push(`- **TFLite Path:** ${result.tflite_path}`);
      lines.push(`- **File Size:** ${result.file_size_mb} MB`);
      break;
    }
    case "quantize_int8": {
      lines.push(`## INT8 Quantization Complete`);
      lines.push(`- **Quantized Path:** ${result.quantized_path}`);
      lines.push(`- **Size Reduction:** ${result.size_reduction_pct}%`);
      break;
    }
    case "fovux_doctor": {
      lines.push(`## Fovux Doctor Health Report`);
      lines.push(`- **Python:** ${result.python}`);
      lines.push(
        `- **GPU Accelerator:** ${result.gpu?.accelerator} (Available: ${result.gpu?.available})`
      );
      lines.push(`- **FOVUX_HOME:** ${result.fovux_home?.path}`);
      break;
    }
    default:
      return undefined;
  }

  return lines.join("\n") + "\n\n---\n";
}
