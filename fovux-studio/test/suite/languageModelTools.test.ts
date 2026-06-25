/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as vscode from "vscode";

import { registerFovuxLanguageModelTool } from "../../src/fovux/languageModelTools";
import { GRANULAR_TOOLS } from "../../src/fovux/tools/definitions";

// Mock the VS Code API
vi.mock("vscode", () => {
  const registeredTools = new Map<string, any>();

  class MarkdownString {
    value = "";
    isTrusted = false;
    appendMarkdown(text: string) {
      this.value += text;
      return this;
    }
  }

  class LanguageModelToolResult {
    constructor(readonly parts: any[]) {}
  }

  class LanguageModelTextPart {
    constructor(readonly value: string) {}
  }

  return {
    lm: {
      registerTool: vi.fn((id: string, tool: any) => {
        registeredTools.set(id, tool);
        return { dispose: vi.fn() };
      }),
      registeredTools, // helper to access registered tools in tests
    },
    MarkdownString,
    LanguageModelToolResult,
    LanguageModelTextPart,
    ExtensionContext: class {},
  };
});

// Mock the MCP Client
const mockCallTool = vi.fn();
vi.mock("../../src/fovux/mcpClient", () => {
  return {
    EmbeddedMcpClient: class {
      async callTool(name: string, args: any) {
        return mockCallTool(name, args);
      }
    },
  };
});

describe("Fovux Language Model Tools", () => {
  const context = {
    subscriptions: [] as any[],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    const mockLm = vscode.lm as any;
    mockLm.registeredTools.clear();
  });

  it("registers all granular tools and the generic tool", () => {
    registerFovuxLanguageModelTool(context as any);

    const mockLm = vscode.lm as any;
    expect(mockLm.registeredTools.has("fovux_call_tool")).toBe(true);

    for (const tool of GRANULAR_TOOLS) {
      expect(mockLm.registeredTools.has(tool.name)).toBe(true);
    }
  });

  describe("prepareInvocation", () => {
    it("generates structured pre-invocation summary for train_start", () => {
      registerFovuxLanguageModelTool(context as any);
      const mockLm = vscode.lm as any;
      const tool = mockLm.registeredTools.get("fovux_start_train");

      const prepared = tool.prepareInvocation({
        input: {
          dataset_path: "/path/to/data",
          model: "yolov8n.pt",
          epochs: 50,
          batch: 8,
          imgsz: 640,
        },
      });

      expect(prepared.invocationMessage).toBe("Running Start Training");
      expect(prepared.confirmationMessages.title).toBe("Run Start Training?");

      const message = prepared.confirmationMessages.message as vscode.MarkdownString;
      expect(message.value).toContain("🚀 Fovux: Start Training Run");
      expect(message.value).toContain("/path/to/data");
      expect(message.value).toContain("yolov8n.pt");
      expect(message.value).toContain("50");
      expect(message.value).toContain("8");
    });

    it("generates structured pre-invocation summary for run_delete", () => {
      registerFovuxLanguageModelTool(context as any);
      const mockLm = vscode.lm as any;
      const tool = mockLm.registeredTools.get("fovux_delete_run");

      const prepared = tool.prepareInvocation({
        input: {
          run_id: "run_to_remove",
          delete_files: true,
        },
      });

      const message = prepared.confirmationMessages.message as vscode.MarkdownString;
      expect(message.value).toContain("🗑️ Fovux: Delete Training Run");
      expect(message.value).toContain("run_to_remove");
      expect(message.value).toContain("permanently delete");
    });

    it("uses default fallback message for non-risky tools", () => {
      registerFovuxLanguageModelTool(context as any);
      const mockLm = vscode.lm as any;
      const tool = mockLm.registeredTools.get("fovux_inspect_dataset");

      const prepared = tool.prepareInvocation({
        input: {
          dataset_path: "/path/to/data",
        },
      });

      expect(prepared.confirmationMessages.message).toBe(
        "Fovux Studio will call dataset_inspect on your local fovux-mcp server."
      );
    });

    it("supports risky tools called through the generic fovux_call_tool fallback", () => {
      registerFovuxLanguageModelTool(context as any);
      const mockLm = vscode.lm as any;
      const tool = mockLm.registeredTools.get("fovux_call_tool");

      const prepared = tool.prepareInvocation({
        input: {
          tool: "train_start",
          args: {
            dataset_path: "/path/to/generic",
            epochs: 25,
          },
        },
      });

      const message = prepared.confirmationMessages.message as vscode.MarkdownString;
      expect(message.value).toContain("🚀 Fovux: Start Training Run");
      expect(message.value).toContain("/path/to/generic");
      expect(message.value).toContain("25");
    });
  });

  describe("invoke", () => {
    it("returns structured summary and JSON parts for dataset_inspect", async () => {
      mockCallTool.mockResolvedValueOnce({
        format_detected: "yolo",
        total_images: 42,
        total_annotations: 13,
        quality_score: 88.5,
        dataset_card: "### Sample Card",
      });

      registerFovuxLanguageModelTool(context as any);
      const mockLm = vscode.lm as any;
      const tool = mockLm.registeredTools.get("fovux_inspect_dataset");

      const result = await tool.invoke({
        input: { dataset_path: "/my/data" },
      });

      expect(mockCallTool).toHaveBeenCalledWith("dataset_inspect", {
        dataset_path: "/my/data",
      });
      expect(result.parts).toHaveLength(2);
      expect(result.parts[0].value).toContain("### Sample Card");
      expect(result.parts[1].value).toContain('"quality_score": 88.5');
    });

    it("returns correct metrics summary for eval_run", async () => {
      mockCallTool.mockResolvedValueOnce({
        map50: 0.85,
        map50_95: 0.65,
        precision: 0.9,
        recall: 0.8,
      });

      registerFovuxLanguageModelTool(context as any);
      const mockLm = vscode.lm as any;
      const tool = mockLm.registeredTools.get("fovux_run_eval");

      const result = await tool.invoke({
        input: { checkpoint: "best.pt", dataset_path: "/my/data" },
      });

      expect(result.parts).toHaveLength(2);
      expect(result.parts[0].value).toContain("## Evaluation Metrics");
      expect(result.parts[0].value).toContain("- **mAP50:** 0.85");
      expect(result.parts[1].value).toContain('"map50": 0.85');
    });
  });
});
