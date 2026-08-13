import { apiUrl } from "./config";
import { ApiError, ApiTimeoutError } from "./errors";

export type ApiRequestOptions = Omit<RequestInit, "signal"> & {
  timeoutMs?: number;
  signal?: AbortSignal;
};

const DEFAULT_TIMEOUT_MS = 10_000;

export async function apiRequest<T>(
  path: string,
  { timeoutMs = DEFAULT_TIMEOUT_MS, signal, headers, body, ...init }: ApiRequestOptions = {},
): Promise<T> {
  if (signal?.aborted) {
    throw signal.reason instanceof Error ? signal.reason : new DOMException("Aborted", "AbortError");
  }
  const timeoutController = new AbortController();
  const abortFromCaller = () => timeoutController.abort(signal?.reason);
  signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeoutId = setTimeout(() => timeoutController.abort(), timeoutMs);
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      body,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(body && !isFormData ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      signal: timeoutController.signal,
    });
    const responseBody = await parseResponseBody(response);
    if (!response.ok) {
      throw new ApiError(response.status, extractDetail(responseBody, response.statusText), responseBody);
    }
    return responseBody as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError" && !signal?.aborted) {
      throw new ApiTimeoutError(timeoutMs);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}

async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const text = await response.text();
  if (!text) return undefined;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return text;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function extractDetail(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  if (typeof body === "string" && body) return body;
  return fallback || "API request failed";
}
