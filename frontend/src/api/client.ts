/**
 * The ONLY place that talks to the network. UI components never call fetch().
 */
import { getApiBase } from "@/lib/config";
import { recordEvent } from "@/lib/eventLog";

export type ApiErrorKind = "config" | "network" | "timeout" | "http" | "parse";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  /** Backend-provided detail when present (FastAPI `detail`). */
  readonly detail: string | null;
  /** Expandable technical text for the "details" disclosure. */
  readonly technical: string;

  constructor(opts: {
    kind: ApiErrorKind;
    message: string;
    status?: number | null;
    detail?: string | null;
    technical?: string;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.kind = opts.kind;
    this.status = opts.status ?? null;
    this.detail = opts.detail ?? null;
    this.technical = opts.technical ?? opts.message;
  }

  /** True when the failure means "the backend is not reachable at all". */
  get isConnectionLoss(): boolean {
    return this.kind === "network" || this.kind === "timeout" || this.kind === "config";
  }
}

/** FastAPI `detail` is a string, or an array of validation errors. */
function normalizeDetail(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join("; ");
  }
  return null;
}

function friendlyHttpMessage(status: number, detail: string | null): string {
  if (detail) return detail;
  if (status === 404) return "Not found.";
  if (status === 503) return "This capability is unavailable in the current backend environment.";
  if (status >= 500) return "The backend reported an internal error.";
  return `Request failed (HTTP ${status}).`;
}

function requireBase(): string {
  const base = getApiBase();
  if (!base) {
    throw new ApiError({
      kind: "config",
      message: "Backend URL is not configured. Set NEXT_PUBLIC_API_BASE_URL and rebuild.",
    });
  }
  return base;
}

export interface RequestOptions {
  method?: "GET" | "POST";
  /** Query parameters; undefined / null values are dropped. */
  query?: Record<string, string | number | null | undefined>;
  timeoutMs?: number;
  signal?: AbortSignal;
  /** Short label used in the client event log (e.g. "Preprocessing"). */
  label?: string;
  /** Skip the client event log (used for background polling). */
  silent?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(requireBase() + path);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function execute(path: string, opts: RequestOptions): Promise<Response> {
  const method = opts.method ?? "GET";
  const started = performance.now();
  const controller = new AbortController();
  const timeoutMs = opts.timeoutMs ?? 30_000;
  const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
  opts.signal?.addEventListener("abort", () => controller.abort(opts.signal?.reason));

  const log = (status: number, ok: boolean, error?: string) => {
    if (opts.silent) return;
    recordEvent({
      method,
      path,
      status,
      ok,
      durationMs: Math.round(performance.now() - started),
      label: opts.label,
      error,
    });
  };

  try {
    const res = await fetch(buildUrl(path, opts.query), { method, signal: controller.signal });
    if (!res.ok) {
      let detail: string | null = null;
      try {
        detail = normalizeDetail(await res.clone().json());
      } catch {
        /* non-JSON error body */
      }
      log(res.status, false, detail ?? undefined);
      throw new ApiError({
        kind: "http",
        status: res.status,
        detail,
        message: friendlyHttpMessage(res.status, detail),
        technical: `${method} ${path} -> HTTP ${res.status}${detail ? ` — ${detail}` : ""}`,
      });
    }
    log(res.status, true);
    return res;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    const timedOut = controller.signal.aborted && controller.signal.reason === "timeout";
    log(0, false, timedOut ? "timeout" : "network");
    if (timedOut) {
      throw new ApiError({
        kind: "timeout",
        message: "The backend took too long to respond.",
        technical: `${method} ${path} timed out after ${timeoutMs} ms`,
      });
    }
    if (opts.signal?.aborted) throw err; // caller cancelled; not an error to display
    throw new ApiError({
      kind: "network",
      message: "Backend connection lost. Check that the API is running and reachable.",
      technical: `${method} ${path} — ${err instanceof Error ? err.message : String(err)}`,
    });
  } finally {
    clearTimeout(timer);
  }
}

export async function requestJson<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await execute(path, opts);
  try {
    return (await res.json()) as T;
  } catch (err) {
    throw new ApiError({
      kind: "parse",
      message: "The backend returned a response this app could not read.",
      technical: `${path} — ${err instanceof Error ? err.message : String(err)}`,
    });
  }
}

export async function requestBlob(
  path: string,
  opts: RequestOptions = {},
): Promise<{ blob: Blob; headers: Headers }> {
  const res = await execute(path, opts);
  return { blob: await res.blob(), headers: res.headers };
}

/**
 * Multipart upload with REAL progress (fetch cannot report upload progress, XHR can).
 * `onProgress` receives bytes sent / total bytes of the request body.
 */
export function uploadFiles<T>(
  path: string,
  files: File[],
  onProgress?: (loaded: number, total: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    let base: string;
    try {
      base = requireBase();
    } catch (e) {
      reject(e);
      return;
    }

    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);

    const started = performance.now();
    const xhr = new XMLHttpRequest();
    xhr.open("POST", base + path);
    xhr.timeout = 10 * 60_000;

    const log = (status: number, ok: boolean, error?: string) =>
      recordEvent({
        method: "POST",
        path,
        status,
        ok,
        durationMs: Math.round(performance.now() - started),
        label: "Input upload",
        error,
      });

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded, e.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* leave null */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        log(xhr.status, true);
        resolve(body as T);
      } else {
        const detail = normalizeDetail(body);
        log(xhr.status, false, detail ?? undefined);
        reject(
          new ApiError({
            kind: "http",
            status: xhr.status,
            detail,
            message: friendlyHttpMessage(xhr.status, detail),
            technical: `POST ${path} -> HTTP ${xhr.status}${detail ? ` — ${detail}` : ""}`,
          }),
        );
      }
    };
    xhr.onerror = () => {
      log(0, false, "network");
      reject(
        new ApiError({
          kind: "network",
          message: "Backend connection lost during upload.",
          technical: `POST ${path} — network error`,
        }),
      );
    };
    xhr.ontimeout = () => {
      log(0, false, "timeout");
      reject(new ApiError({ kind: "timeout", message: "The upload timed out.", technical: `POST ${path} timed out` }));
    };
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    xhr.send(form);
  });
}

export function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () =>
      reject(new ApiError({ kind: "parse", message: "Could not read the preview image.", technical: String(reader.error) }));
    reader.readAsDataURL(blob);
  });
}
