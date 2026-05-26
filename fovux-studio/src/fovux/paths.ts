/**
 * FOVUX_HOME resolution for the VS Code extension.
 *
 * Priority:
 * 1. fovux.home VS Code setting
 * 2. FOVUX_HOME environment variable
 * 3. ~/.fovux
 */

import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";

export interface FovuxProfile {
  name: string;
  home: string;
}

let sessionActiveProfile: string | null = null;

export function resolveFovuxHome(): string {
  const config = vscode.workspace.getConfiguration("fovux");
  const activeProfile =
    sessionActiveProfile ?? config.get<string>("activeProfile");
  const profile = resolveFovuxProfiles().find(
    (candidate) => candidate.name === activeProfile,
  );
  if (profile) {
    return expandHome(profile.home);
  }
  const configHome = config.get<string>("home");
  if (configHome && configHome.trim() !== "") {
    return expandHome(configHome);
  }
  const envHome = process.env["FOVUX_HOME"];
  if (envHome && envHome.trim() !== "") {
    return expandHome(envHome);
  }
  return path.join(os.homedir(), ".fovux");
}

export function setSessionActiveFovuxProfile(profileName: string | null): void {
  sessionActiveProfile = profileName;
}

export function getSessionActiveFovuxProfile(): string | null {
  return sessionActiveProfile;
}

export function resolveFovuxProfiles(): FovuxProfile[] {
  const config = vscode.workspace.getConfiguration("fovux");
  const rawProfiles = config.get<unknown>("profiles") ?? [];
  if (!Array.isArray(rawProfiles)) {
    return [];
  }
  return rawProfiles.filter(isFovuxProfile).map((profile) => ({
    name: profile.name.trim(),
    home: expandHome(profile.home.trim()),
  }));
}

function expandHome(p: string): string {
  if (p.startsWith("~")) {
    return path.join(os.homedir(), p.slice(1));
  }
  return p;
}

function isFovuxProfile(value: unknown): value is FovuxProfile {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    typeof record["name"] === "string" &&
    record["name"].trim() !== "" &&
    typeof record["home"] === "string" &&
    record["home"].trim() !== ""
  );
}
