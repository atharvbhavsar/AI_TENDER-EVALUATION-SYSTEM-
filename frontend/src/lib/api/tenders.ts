/**
 * API service for Tender Management, Publishing, and Public Tender Portal.
 */

import { api, apiClient } from "./client";
import { getApiUrl } from "../config";
import type { TenderItem, TenderListResponse, TenderVersionItem } from "./dashboard";

export type { TenderItem, TenderListResponse, TenderVersionItem };

export interface CreateTenderPayload {
  tender_number: string;
  title: string;
  description?: string;
  issuing_authority?: string;
  initial_version_label?: string;
  initial_change_summary?: string;
}

export interface UpdateTenderPayload {
  title?: string;
  description?: string;
  issuing_authority?: string;
  status?: "DRAFT" | "PUBLISHED" | "CLOSED" | "CANCELLED";
}

export interface PublicDocumentItem {
  id: string;
  filename: string;
  file_extension: string;
  file_size: number;
  document_type: string;
  created_at: string;
}

export interface PublicDocumentListResponse {
  items: PublicDocumentItem[];
  total: number;
}

/**
 * Authenticated officer: List all tenders with optional filters
 */
export async function listTenders(
  page = 1,
  pageSize = 10,
  status?: string,
  search?: string
): Promise<TenderListResponse> {
  return api.get<TenderListResponse>("/tenders", {
    params: {
      page,
      page_size: pageSize,
      status: status || undefined,
      search: search || undefined,
    },
  });
}

/**
 * Authenticated officer: Retrieve full tender details
 */
export async function getTender(tenderId: string): Promise<TenderItem> {
  return api.get<TenderItem>(`/tenders/${tenderId}`);
}

/**
 * Authenticated officer: Create new tender
 */
export async function createTender(payload: CreateTenderPayload): Promise<TenderItem> {
  return api.post<TenderItem>("/tenders", payload);
}

/**
 * Authenticated officer: Update tender metadata
 */
export async function updateTender(tenderId: string, payload: UpdateTenderPayload): Promise<TenderItem> {
  return api.patch<TenderItem>(`/tenders/${tenderId}`, payload);
}

/**
 * Authenticated officer: Publish a draft tender
 */
export async function publishTender(tenderId: string): Promise<TenderItem> {
  return api.post<TenderItem>(`/tenders/${tenderId}/publish`, {});
}

/**
 * Public unauthenticated: List all published or closed tenders
 */
export async function listPublicTenders(
  page = 1,
  pageSize = 10,
  search?: string,
  status?: "PUBLISHED" | "CLOSED"
): Promise<TenderListResponse> {
  return apiClient<TenderListResponse>("/tenders/public", {
    skipAuth: true,
    params: {
      page,
      page_size: pageSize,
      search: search || undefined,
      status: status || undefined,
    },
  });
}

/**
 * Public unauthenticated: Retrieve single published tender details
 */
export async function getPublicTender(tenderId: string): Promise<TenderItem> {
  return apiClient<TenderItem>(`/tenders/public/${tenderId}`, {
    skipAuth: true,
  });
}

/**
 * Public unauthenticated: List publicly downloadable documents for a published tender
 */
export async function listPublicTenderDocuments(tenderId: string): Promise<PublicDocumentListResponse> {
  return apiClient<PublicDocumentListResponse>(`/tenders/public/${tenderId}/documents`, {
    skipAuth: true,
  });
}

/**
 * Helper to construct the secure public document download URL
 */
export function getPublicDocumentDownloadUrl(tenderId: string, documentId: string): string {
  return getApiUrl(`/tenders/public/${tenderId}/documents/${documentId}/download`);
}
