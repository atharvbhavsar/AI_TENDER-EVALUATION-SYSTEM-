/**
 * Authentication API module.
 * Directly maps to backend endpoints: /api/v1/auth/login and /api/v1/auth/me.
 */

import { api } from "./client";
import { setAccessToken, clearAccessToken } from "./token";
import type { LoginRequest, RegisterBidderRequest, TokenResponse, UserResponse } from "@/types/auth";

export async function loginUser(credentials: LoginRequest): Promise<TokenResponse> {
  const data = await api.post<TokenResponse>("/auth/login", credentials, { skipAuth: true });
  if (data?.access_token) {
    setAccessToken(data.access_token);
  }
  return data;
}

export async function registerBidder(payload: RegisterBidderRequest): Promise<TokenResponse> {
  const data = await api.post<TokenResponse>("/auth/register", payload, { skipAuth: true });
  if (data?.access_token) {
    setAccessToken(data.access_token);
  }
  return data;
}

export async function fetchCurrentUser(): Promise<UserResponse> {
  return api.get<UserResponse>("/auth/me");
}

export function logoutUser(): void {
  clearAccessToken();
}
