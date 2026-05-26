/**
 * Cross-package compatibility contract between fovux-studio and fovux-mcp.
 *
 * Defines supported version ranges and classification logic for the
 * connected server version.
 */

/** Compatibility version ranges using semver notation. */
export const FOVUX_COMPAT = {
  /** Minimum server version required for any functionality. */
  required: ">=4.0.0 <5.0.0",
  /** Recommended server version range for full feature parity. */
  recommended: ">=4.1.0 <5.0.0",
  /** Exact version this Studio build was tested against. */
  testedAgainst: "4.1.4",
} as const;

/** Possible compatibility classifications. */
export type CompatState =
  | "connected:recommended"
  | "connected:supported"
  | "incompatible";

/**
 * Parse a semver version string into major.minor.patch components.
 * Returns null for invalid version strings.
 */
function parseSemver(
  version: string,
): { major: number; minor: number; patch: number } | null {
  const match = /^(\d+)\.(\d+)\.(\d+)/.exec(version.trim());
  if (!match) {
    return null;
  }
  return {
    major: parseInt(match[1], 10),
    minor: parseInt(match[2], 10),
    patch: parseInt(match[3], 10),
  };
}

/**
 * Check if a version satisfies a simple semver range.
 * Supports ranges like ">=4.0.0 <5.0.0".
 */
function satisfiesRange(version: string, range: string): boolean {
  const parsed = parseSemver(version);
  if (!parsed) {
    return false;
  }

  const constraints = range.split(/\s+/);
  for (const constraint of constraints) {
    const geMatch = /^>=(\d+)\.(\d+)\.(\d+)$/.exec(constraint);
    if (geMatch) {
      const min = {
        major: parseInt(geMatch[1], 10),
        minor: parseInt(geMatch[2], 10),
        patch: parseInt(geMatch[3], 10),
      };
      const v = parsed.major * 1_000_000 + parsed.minor * 1_000 + parsed.patch;
      const m = min.major * 1_000_000 + min.minor * 1_000 + min.patch;
      if (v < m) {
        return false;
      }
      continue;
    }

    const ltMatch = /^<(\d+)\.(\d+)\.(\d+)$/.exec(constraint);
    if (ltMatch) {
      const max = {
        major: parseInt(ltMatch[1], 10),
        minor: parseInt(ltMatch[2], 10),
        patch: parseInt(ltMatch[3], 10),
      };
      const v = parsed.major * 1_000_000 + parsed.minor * 1_000 + parsed.patch;
      const m = max.major * 1_000_000 + max.minor * 1_000 + max.patch;
      if (v >= m) {
        return false;
      }
      continue;
    }
  }
  return true;
}

/**
 * Classify the connected server version into a compatibility state.
 *
 * @param serverVersion - The version string returned by the server's /health endpoint.
 *                        If null or undefined, the server is classified as incompatible.
 */
export function classifyCompat(
  serverVersion: string | null | undefined,
): CompatState {
  if (!serverVersion) {
    return "incompatible";
  }

  if (!satisfiesRange(serverVersion, FOVUX_COMPAT.required)) {
    return "incompatible";
  }

  if (satisfiesRange(serverVersion, FOVUX_COMPAT.recommended)) {
    return "connected:recommended";
  }

  return "connected:supported";
}
