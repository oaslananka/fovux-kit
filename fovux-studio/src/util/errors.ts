/**
 * Fovux Studio error types.
 */

export class FovuxStudioError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FovuxStudioError";
  }
}

export class FovuxHttpError extends FovuxStudioError {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(`HTTP ${status}: ${message}`);
    this.name = "FovuxHttpError";
  }
}
