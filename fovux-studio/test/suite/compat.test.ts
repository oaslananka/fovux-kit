/**
 * Tests for the cross-package compatibility contract.
 */

import { describe, it, expect } from "vitest";
import { classifyCompat, FOVUX_COMPAT } from "../../src/fovux/compat";

describe("FOVUX_COMPAT constants", () => {
  it("has required, recommended, and testedAgainst fields", () => {
    expect(FOVUX_COMPAT.required).toBe(">=4.0.0 <5.0.0");
    expect(FOVUX_COMPAT.recommended).toBe(">=4.1.0 <5.0.0");
    expect(FOVUX_COMPAT.testedAgainst).toBe("4.1.4");
  });
});

describe("classifyCompat", () => {
  it("classifies 4.1.0 as recommended", () => {
    expect(classifyCompat("4.1.0")).toBe("connected:recommended");
  });

  it("classifies 4.2.0 as recommended", () => {
    expect(classifyCompat("4.2.0")).toBe("connected:recommended");
  });

  it("classifies 4.99.99 as recommended", () => {
    expect(classifyCompat("4.99.99")).toBe("connected:recommended");
  });

  it("classifies 4.0.0 as supported", () => {
    expect(classifyCompat("4.0.0")).toBe("connected:supported");
  });

  it("classifies 4.0.5 as supported", () => {
    expect(classifyCompat("4.0.5")).toBe("connected:supported");
  });

  it("classifies 3.9.0 as incompatible", () => {
    expect(classifyCompat("3.9.0")).toBe("incompatible");
  });

  it("classifies 5.0.0 as incompatible", () => {
    expect(classifyCompat("5.0.0")).toBe("incompatible");
  });

  it("classifies null as incompatible", () => {
    expect(classifyCompat(null)).toBe("incompatible");
  });

  it("classifies undefined as incompatible", () => {
    expect(classifyCompat(undefined)).toBe("incompatible");
  });

  it("classifies empty string as incompatible", () => {
    expect(classifyCompat("")).toBe("incompatible");
  });

  it("classifies garbage as incompatible", () => {
    expect(classifyCompat("not-a-version")).toBe("incompatible");
  });
});
