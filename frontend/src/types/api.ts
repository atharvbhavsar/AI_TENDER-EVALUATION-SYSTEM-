/**
 * API request, response, and error types aligned with FastAPI error handlers and health endpoints.
 */

export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
  ctx?: Record<string, unknown>;
}

export interface APIError {
  message: string;
  statusCode: number;
  statusType:
    | "UNAUTHORIZED"
    | "FORBIDDEN"
    | "NOT_FOUND"
    | "VALIDATION_ERROR"
    | "RATE_LIMITED"
    | "SERVER_ERROR"
    | "NETWORK_ERROR"
    | "TIMEOUT"
    | "UNKNOWN";
  detail?: string | ValidationErrorDetail[];
  raw?: unknown;
}

export type AsyncState<T> =
  | { status: "IDLE"; data: null; error: null }
  | { status: "LOADING"; data: null; error: null }
  | { status: "SUCCESS"; data: T; error: null }
  | { status: "EMPTY"; data: T; error: null }
  | { status: "ERROR"; data: null; error: APIError };

export interface HealthResponse {
  status: string;
  app_name?: string;
  version?: string;
  environment?: string;
  database?: string;
  redis?: string;
  timestamp?: string;
}

export interface LivenessResponse {
  status: string;
}

export interface ReadinessResponse {
  status: "ready" | "not_ready";
  components: {
    database: { status: string; error?: string };
    storage?: { status: string; error?: string };
    opa?: { status: string; code?: number };
    redis: { status: string };
  };
}

export interface PaginationMeta {
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginationMeta;
}
