import * as vscode from "vscode";

import type { UserPreset } from "../webviews/shared/types";

const USER_PRESETS_KEY = "fovux.userPresets";

export function getUserPresets(context: vscode.ExtensionContext): UserPreset[] {
  if (!context.globalState) {
    return [];
  }
  const value = context.globalState.get<unknown>(USER_PRESETS_KEY, []);
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isUserPreset);
}

export async function saveUserPreset(
  context: vscode.ExtensionContext,
  preset: UserPreset
): Promise<UserPreset[]> {
  const presets = [
    preset,
    ...getUserPresets(context).filter((candidate) => candidate.name !== preset.name),
  ].slice(0, 20);
  await context.globalState?.update(USER_PRESETS_KEY, presets);
  return presets;
}

export async function deleteUserPreset(
  context: vscode.ExtensionContext,
  name: string
): Promise<UserPreset[]> {
  const presets = getUserPresets(context).filter((preset) => preset.name !== name);
  await context.globalState?.update(USER_PRESETS_KEY, presets);
  return presets;
}

function isUserPreset(value: unknown): value is UserPreset {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  const config = record["config"];
  return (
    typeof record["name"] === "string" &&
    typeof record["createdAt"] === "string" &&
    !!config &&
    typeof config === "object"
  );
}
