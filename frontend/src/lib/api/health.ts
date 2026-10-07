/**
 * Health check and dependency diagnostics API module.
 * Maps to backend endpoints: /api/v1/health, /api/v1/health/live, /api/v1/health/ready.
 */

import { api } from "./client";
import type { HealthResponse, LivenessResponse, ReadinessResponse } from "@/types/api";

export async function fetchHealth(): Promise<HealthResponse> {
  return api.get<HealthResponse>("/health", { skipAuth: true, timeoutMs: 5000 });
}

export async function fetchLiveness(): Promise<LivenessResponse> {
  return api.get<LivenessResponse>("/health/live", { skipAuth: true, timeoutMs: 3000 });
}

export async function fetchReadiness(): Promise<ReadinessResponse> {
  return api.get<ReadinessResponse>("/health/ready", { skipAuth: true, timeoutMs: 5000 });
}
