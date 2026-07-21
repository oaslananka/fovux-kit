/**
 * Custom confirmation templates retained by the Studio UX layer.
 */
export type ConfirmationKind =
  | "train_start"
  | "train_stop"
  | "train_resume"
  | "export_onnx"
  | "export_tflite"
  | "quantize_int8"
  | "run_delete"
  | "run_tag";

/**
 * Type definition for a generated granular LM tool registration.
 */
export interface GranularToolDefinition {
  /** Unique tool name registered with VS Code LM API. */
  name: string;
  /** Reference name for prompt mentions. */
  toolReferenceName: string;
  /** Human-readable display name. */
  displayName: string;
  /** User-facing description shown in VS Code UI. */
  userDescription: string;
  /** LLM-facing description (max 1024 chars). */
  modelDescription: string;
  /** Tags for filtering. */
  tags: string[];
  /** Whether this tool can be referenced in prompts. */
  canBeReferencedInPrompt: boolean;
  /** Corresponding fovux-mcp tool name. */
  mcpToolName: string;
  /** Canonical backend JSON Schema for the tool input. */
  inputSchema: Record<string, unknown>;
  /** Whether the backend HTTP policy requires explicit confirmation. */
  requiresConfirmation: boolean;
  /** Backend authorization scope required by the tool. */
  requiredScope: string;
  /** Backend policy category used for audit and UX decisions. */
  policyCategory: string;
  /** Optional Studio-specific rich confirmation template. */
  confirmationKind?: ConfirmationKind;
}
