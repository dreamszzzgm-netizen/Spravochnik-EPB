export class ApiError extends Error {
  readonly name = "ApiError";

  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly body?: unknown,
  ) {
    super(detail);
  }
}

export class ApiTimeoutError extends Error {
  readonly name = "ApiTimeoutError";

  constructor(public readonly timeoutMs: number) {
    super(`API request timed out after ${timeoutMs} ms`);
  }
}
