const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX ?? "/api/v1";
const REQUEST_TIMEOUT_MS = 30_000;

/** Resolve API base URL from env, falling back to same host as the page on port 8000. */
export function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${API_PREFIX}${normalized}`;
}

export function wsUrl(): string {
  const base = getApiBaseUrl().replace(/^https/, "wss").replace(/^http/, "ws");
  return `${base}${API_PREFIX}/ws`;
}

async function fetchWithTimeout(
  input: string,
  init?: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs / 1000}s`);
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

async function parseError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.detail) {
      if (Array.isArray(json.detail)) {
        return json.detail
          .map((item: { loc?: unknown[]; msg?: string }) => {
            const loc = Array.isArray(item.loc) ? item.loc.join(".") : "";
            return loc ? `${loc}: ${item.msg ?? "validation error"}` : String(item.msg ?? item);
          })
          .join("; ");
      }
      return String(json.detail);
    }
  } catch {
    /* use raw text */
  }
  return text || `${res.status} error`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), { cache: "no-store" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
