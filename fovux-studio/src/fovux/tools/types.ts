/**
 * Type definition for a granular LM tool registration.
 */
export interface GranularToolDefinition {
  /** Unique tool name registered with VS Code LM API. */
  name: string;
  /** Reference name for prompt mentions. */
  toolReferenceName: string;
  /** Human-readable display name. */
  displayName: string;
  /** LLM-facing description (max 1024 chars). */
  modelDescription: string;
  /** Tags for filtering. */
  tags: string[];
  /** Whether this tool can be referenced in prompts. */
  canBeReferencedInPrompt: boolean;
  /** Corresponding fovux-mcp tool name. */
  mcpToolName: string;
  /** JSON Schema for the tool input. */
  inputSchema: Record<string, unknown>;
}
