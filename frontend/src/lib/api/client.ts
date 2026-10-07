/**
 * Centralized API Client for CRPF Tender Evaluation Backend.
 * Standardizes fetch requests, authorization headers, timeout handling, and unified error mapping.
 */

import { APP_CONFIG, getApiUrl } from "../config";
import { getAccessToken } from "./token";
import type { APIError } from "@/types/api";

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  skipAuth?: boolean;
  params?: Record<string, string | number | boolean | undefined | null>;
}

export class ApiClientError extends Error {
  public readonly info: APIError;

  constructor(info: APIError) {
    super(info.message);
    this.name = "ApiClientError";
    this.info = info;
  }
}

function classifyStatusCode(statusCode: number): APIError["statusType"] {
  if (statusCode === 401) return "UNAUTHORIZED";
  if (statusCode === 403) return "FORBIDDEN";
  if (statusCode === 404) return "NOT_FOUND";
  if (statusCode === 422) return "VALIDATION_ERROR";
  if (statusCode === 429) return "RATE_LIMITED";
  if (statusCode >= 500) return "SERVER_ERROR";
  return "UNKNOWN";
}

type UnauthorizedListener = () => void;
let unauthorizedListener: UnauthorizedListener | null = null;

export function setOnUnauthorizedHandler(listener: UnauthorizedListener | null) {
  unauthorizedListener = listener;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    timeoutMs = APP_CONFIG.requestTimeoutMs,
    skipAuth = false,
    params,
    headers: customHeaders,
    ...fetchOptions
  } = options;

  // Build target URL with query params
  let targetUrl = getApiUrl(endpoint);
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      targetUrl += (targetUrl.includes("?") ? "&" : "?") + queryString;
    }
  }

  // Build request headers
  const headers = new Headers(customHeaders);
  
  // Set Content-Type only if not sending FormData
  const isFormData = typeof FormData !== "undefined" && fetchOptions.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  // Inject Authorization Bearer token if present
  if (!skipAuth) {
    const token = getAccessToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  // Setup timeout with AbortController
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(targetUrl, {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Handle 204 No Content
    if (response.status === 204) {
      return null as unknown as T;
    }

    // Try parsing response body
    const contentType = response.headers.get("content-type") || "";
    let data: unknown = null;
    if (contentType.includes("application/json")) {
      try {
        data = await response.json();
      } catch {
        data = null;
      }
    } else {
      try {
        data = await response.text();
      } catch {
        data = null;
      }
    }

    if (!response.ok) {
      let errorMessage = "An error occurred while communicating with the server.";
      let detail: unknown = undefined;

      if (data && typeof data === "object") {
        const errorBody = data as Record<string, unknown>;
        if (typeof errorBody.detail === "string") {
          errorMessage = errorBody.detail;
          detail = errorBody.detail;
        } else if (Array.isArray(errorBody.detail)) {
          // FastAPI validation error array
          errorMessage = "Validation error in request parameters.";
          detail = errorBody.detail;
        } else if (errorBody.errors) {
          detail = errorBody.errors;
        }
      } else if (typeof data === "string" && data.trim()) {
        errorMessage = data.slice(0, 200);
      }

      if (response.status === 401) {
        errorMessage = errorMessage || "Authentication required. Please sign in.";
        if (!skipAuth) {
          try {
            unauthorizedListener?.();
          } catch {
            // Ignore callback failures
          }
        }
      } else if (response.status === 403) {
        errorMessage = errorMessage || "You do not have permission to access this resource.";
      } else if (response.status === 404) {
        errorMessage = errorMessage || "The requested resource was not found.";
      } else if (response.status >= 500) {
        errorMessage = "A server error occurred. Please contact the administrator.";
      }

      const apiError: APIError = {
        message: errorMessage,
        statusCode: response.status,
        statusType: classifyStatusCode(response.status),
        detail: detail as APIError["detail"],
        raw: data,
      };

      throw new ApiClientError(apiError);
    }

    return data as T;
  } catch (error: unknown) {
    clearTimeout(timeoutId);

    if (error instanceof ApiClientError) {
      throw error;
    }

    // Check for Abort / Timeout
    if (error instanceof DOMException && error.name === "AbortError") {
      const timeoutError: APIError = {
        message: `Request timed out after ${timeoutMs / 1000}s.`,
        statusCode: 408,
        statusType: "TIMEOUT",
      };
      throw new ApiClientError(timeoutError);
    }

    // Network error (backend offline, CORS blocked, connection refused)
    const networkError: APIError = {
      message: "Unable to connect to backend server. Please verify backend is running.",
      statusCode: 0,
      statusType: "NETWORK_ERROR",
      raw: error,
    };
    throw new ApiClientError(networkError);
  }
}

// HTTP Helper Methods
export const api = {
  get<T>(endpoint: string, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return apiClient<T>(endpoint, { ...options, method: "GET" });
  },

  post<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return apiClient<T>(endpoint, {
      ...options,
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  },

  put<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return apiClient<T>(endpoint, {
      ...options,
      method: "PUT",
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  },

  patch<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">): Promise<T> {
    return apiClient<T>(endpoint, {
      ...options,
      method: "PATCH",
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  },

  delete<T>(endpoint: string, options?: Omit<RequestOptions, "method">): Promise<T> {
    return apiClient<T>(endpoint, { ...options, method: "DELETE" });
  },
};
