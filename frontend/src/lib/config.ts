/**
 * Centralized Application Configuration.
 * Strictly accesses public configuration via NEXT_PUBLIC_* variables.
 * NO secrets or sensitive credentials allowed here.
 */

export const APP_CONFIG = {
  appName: "CRPF AI Tender Evaluation Platform",
  appSubtitle: "Central Reserve Police Force — Procurement & Technical Eligibility",
  version: "1.0.0",
  apiBaseUrl: (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, ""),
  apiV1Prefix: "/api/v1",
  requestTimeoutMs: 30000,
} as const;

export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  // If path already has /api/v1 prefix, don't duplicate
  if (cleanPath.startsWith("/api/v1/")) {
    return `${APP_CONFIG.apiBaseUrl}${cleanPath}`;
  }
  return `${APP_CONFIG.apiBaseUrl}${APP_CONFIG.apiV1Prefix}${cleanPath}`;
}
