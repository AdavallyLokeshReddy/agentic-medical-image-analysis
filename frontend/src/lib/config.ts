/**
 * Runtime configuration.
 *
 * NEXT_PUBLIC_API_BASE_URL is inlined at build time. In production it MUST be
 * set; there is deliberately no silent localhost fallback outside development,
 * so a misconfigured deployment shows a clear error instead of a dead app.
 */
export function getApiBase(): string | null {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  if (process.env.NODE_ENV !== "production") return "http://localhost:8000";
  return null;
}

export const NOTICE_SHORT = "Research & engineering prototype · Not for clinical diagnosis or treatment";

export const NOTICE_LONG =
  "This is a research and engineering prototype exploring governed agentic AI for medical imaging. " +
  "It is not a clinically validated medical device and must not be used for diagnosis, treatment, or any clinical decision.";
