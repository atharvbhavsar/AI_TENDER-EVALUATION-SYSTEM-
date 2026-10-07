/**
 * Bidder Portal API Service.
 * Interacts directly with /api/v1/bidder/* endpoints.
 */

import { api } from "./client";
import { getAccessToken } from "./token";
import { getApiUrl } from "../config";

export interface BidderProfile {
  id: string;
  email: string;
  full_name: string;
  company_name: string | null;
  phone: string | null;
  is_active: boolean;
  roles: string[];
  permissions: string[];
  created_at: string;
  active_applications_count: number;
}

export interface UpdateBidderProfilePayload {
  full_name?: string;
  company_name?: string;
  phone?: string;
}

export type SubmissionStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "RECEIVED"
  | "PROCESSING"
  | "READY"
  | "REVIEW";

export interface ApplicationSummaryItem {
  id: string;
  submission_reference: string;
  status: SubmissionStatus;
  tender_id: string;
  tender_number: string;
  tender_title: string;
  issuing_authority: string;
  tender_status: string;
  tender_version_id: string;
  version_number: number;
  version_label: string;
  created_at: string;
  updated_at: string;
  documents_count: number;
  bidder_notes?: string | null;
  commercial_quote?: number | null;
  declaration_signed: boolean;
  submitted_at?: string | null;
  is_locked: boolean;
  submission_deadline?: string | null;
}

export interface ApplicationListResponse {
  items: ApplicationSummaryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CriterionChecklistItem {
  id: string;
  criterion_code: string;
  name: string;
  description: string | null;
  category: string;
  mandatory: boolean;
  required_evidence: string | null;
}

export interface BidderDocument {
  id: string;
  tender_id: string;
  tender_version_id: string;
  bid_submission_id: string;
  criterion_id: string | null;
  filename: string;
  content_type: string;
  file_extension: string;
  file_size: number;
  sha256_hash: string;
  document_type: string;
  processing_status: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentDeleteResponse {
  success: boolean;
  message: string;
}

export interface ApplicationDetailResponse {
  id: string;
  submission_reference: string;
  status: SubmissionStatus;
  created_at: string;
  updated_at: string;
  bidder_notes: string | null;
  commercial_quote: number | null;
  declaration_signed: boolean;
  submitted_at: string | null;
  is_locked: boolean;
  tender_id: string;
  tender_number: string;
  tender_title: string;
  tender_description: string | null;
  issuing_authority: string;
  tender_status: string;
  submission_deadline: string | null;
  is_deadline_passed: boolean;
  can_edit: boolean;
  can_submit: boolean;
  tender_version_id: string;
  version_number: number;
  version_label: string;
  criteria_checklist: CriterionChecklistItem[];
  documents: BidderDocument[];
  documents_count: number;
}

export interface UpdateApplicationDraftPayload {
  bidder_notes?: string;
  commercial_quote?: number;
  declaration_signed?: boolean;
}

export interface SubmitApplicationPayload {
  confirm_declaration: boolean;
  bidder_notes?: string;
  commercial_quote?: number;
}

export interface BidderDashboardMetrics {
  company_name: string;
  full_name: string;
  total_applications: number;
  draft_count: number;
  submitted_count: number;
  received_count: number;
  processing_count: number;
  ready_count: number;
  review_count: number;
  available_tenders_count: number;
  recent_applications: ApplicationSummaryItem[];
}

/**
 * Retrieve corporate profile for the authenticated bidder.
 */
export async function getBidderProfile(): Promise<BidderProfile> {
  return api.get<BidderProfile>("/bidder/profile");
}

/**
 * Update bidder representative, company name, or phone.
 */
export async function updateBidderProfile(payload: UpdateBidderProfilePayload): Promise<BidderProfile> {
  return api.patch<BidderProfile>("/bidder/profile", payload);
}

/**
 * Retrieve live operational dashboard metrics for bidder command center.
 */
export async function getBidderDashboard(): Promise<BidderDashboardMetrics> {
  return api.get<BidderDashboardMetrics>("/bidder/dashboard");
}

/**
 * List applications belonging strictly to the authenticated bidder.
 */
export async function listBidderApplications(
  page = 1,
  pageSize = 20,
  status?: SubmissionStatus
): Promise<ApplicationListResponse> {
  return api.get<ApplicationListResponse>("/bidder/applications", {
    params: {
      page,
      page_size: pageSize,
      status: status || undefined,
    },
  });
}

/**
 * Retrieve full application details, tender specs, and requirements checklist.
 */
export async function getBidderApplication(applicationId: string): Promise<ApplicationDetailResponse> {
  return api.get<ApplicationDetailResponse>(`/bidder/applications/${applicationId}`);
}

/**
 * Register new bid application for an open published tender.
 */
export async function applyForTender(tenderId: string): Promise<ApplicationSummaryItem> {
  return api.post<ApplicationSummaryItem>(`/bidder/apply/${tenderId}`, {});
}

/**
 * Save draft bid application updates (remarks, commercial quote, declaration).
 */
export async function updateApplicationDraft(
  applicationId: string,
  payload: UpdateApplicationDraftPayload
): Promise<ApplicationDetailResponse> {
  return api.patch<ApplicationDetailResponse>(`/bidder/applications/${applicationId}`, payload);
}

/**
 * Formally submit and seal the bidder's application.
 */
export async function submitApplication(
  applicationId: string,
  payload: SubmitApplicationPayload
): Promise<ApplicationDetailResponse> {
  return api.post<ApplicationDetailResponse>(`/bidder/applications/${applicationId}/submit`, payload);
}

/**
 * Upload a document against an application and optionally associate with a criterion.
 */
export async function uploadApplicationDocument(
  applicationId: string,
  file: File,
  criterionId?: string,
  documentType: string = "UNKNOWN"
): Promise<BidderDocument> {
  const formData = new FormData();
  formData.append("file", file);
  if (criterionId) {
    formData.append("criterion_id", criterionId);
  }
  formData.append("document_type", documentType);

  return api.post<BidderDocument>(`/bidder/applications/${applicationId}/documents`, formData);
}

/**
 * List all documents associated with an application.
 */
export async function listApplicationDocuments(applicationId: string): Promise<BidderDocument[]> {
  return api.get<BidderDocument[]>(`/bidder/applications/${applicationId}/documents`);
}

/**
 * Delete a document from an application (only when not submitted and before deadline).
 */
export async function deleteApplicationDocument(
  applicationId: string,
  documentId: string
): Promise<DocumentDeleteResponse> {
  return api.delete<DocumentDeleteResponse>(`/bidder/applications/${applicationId}/documents/${documentId}`);
}

/**
 * Download a document binary securely by streaming from backend.
 */
export async function downloadApplicationDocument(
  applicationId: string,
  documentId: string,
  filename: string
): Promise<void> {
  const targetUrl = getApiUrl(`/bidder/applications/${applicationId}/documents/${documentId}/download`);
  const token = getAccessToken();

  const response = await fetch(targetUrl, {
    method: "GET",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    let errorDetail = "Failed to download document.";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // Use fallback
    }
    throw new Error(errorDetail);
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = downloadUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.URL.revokeObjectURL(downloadUrl);
}

