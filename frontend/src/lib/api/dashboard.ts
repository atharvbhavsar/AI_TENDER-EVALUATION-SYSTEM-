/**
 * Procurement Dashboard API Service.
 * Consumes real backend APIs from FastAPI without fabricating any metrics.
 */

import { api } from "./client";

export interface TenderVersionItem {
  id: string;
  tender_id: string;
  version_number: number;
  version_label: string;
  effective_at: string;
  change_summary?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TenderItem {
  id: string;
  tender_number: string;
  title: string;
  description?: string | null;
  issuing_authority: string;
  status: "DRAFT" | "PUBLISHED" | "CLOSED" | "CANCELLED";
  created_by: string;
  created_at: string;
  updated_at: string;
  active_version?: TenderVersionItem | null;
}

export interface TenderListResponse {
  items: TenderItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ReviewCaseItem {
  id: string;
  tender_id: string;
  tender_version_id: string;
  bidder_id: string;
  bid_submission_id: string;
  status: "OPEN" | "IN_REVIEW" | "RESOLVED";
  priority: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  issue_type: string;
  title: string;
  description?: string | null;
  assigned_to?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewCaseListResponse {
  total: number;
  items: ReviewCaseItem[];
}

export interface ReportItem {
  id: string;
  tender_id?: string | null;
  tender_version_id?: string | null;
  bidder_id?: string | null;
  bid_submission_id?: string | null;
  report_type: string;
  status: "GENERATING" | "COMPLETED" | "FAILED";
  title: string;
  file_hash?: string | null;
  file_size_bytes?: number | null;
  created_at: string;
}

export interface ReportListResponse {
  total: number;
  items: ReportItem[];
}

export interface AuditLogItem {
  id: string;
  timestamp: string;
  actor_id?: string | null;
  actor_role?: string | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  tender_id?: string | null;
  reason?: string | null;
}

export interface AuditListResponse {
  total: number;
  items: AuditLogItem[];
}

export interface DocumentBatchItemStatus {
  document_id: string;
  job_id?: string | null;
  filename: string;
  file_extension: string;
  document_type: string;
  status: "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED" | "RETRYING";
  attempt_count: number;
  error_code?: string | null;
}

export interface DocumentBatchStatusResponse {
  total: number;
  completed: number;
  processing: number;
  queued: number;
  failed: number;
  retrying: number;
  is_complete: boolean;
  batch_type: string;
  tender_id?: string | null;
  tender_version_id?: string | null;
  items: DocumentBatchItemStatus[];
}

export interface DashboardMetrics {
  tenders: {
    total: number;
    active: number;
    draft: number;
    closed: number;
    cancelled: number;
    recent: TenderItem[];
    error?: string;
  };
  reviews: {
    open: number;
    inReview: number;
    resolved: number;
    itemsNeedingAttention: ReviewCaseItem[];
    error?: string;
  };
  reports: {
    total: number;
    recent: ReportItem[];
    error?: string;
  };
  processing: {
    available: boolean;
    total: number;
    completed: number;
    processing: number;
    queued: number;
    failed: number;
    failedItems: DocumentBatchItemStatus[];
    error?: string;
  };
  auditLogs: {
    total: number;
    recent: AuditLogItem[];
    error?: string;
  };
  timestamp: string;
}

export async function fetchTendersList(page = 1, pageSize = 10, status?: string): Promise<TenderListResponse> {
  return api.get<TenderListResponse>("/tenders", {
    params: {
      page,
      page_size: pageSize,
      status: status || undefined,
    },
  });
}

export async function fetchReviewCases(status?: string, limit = 10): Promise<ReviewCaseListResponse> {
  return api.get<ReviewCaseListResponse>("/reviews", {
    params: {
      status: status || undefined,
      limit,
    },
  });
}

export async function fetchReportsList(limit = 10): Promise<ReportListResponse> {
  return api.get<ReportListResponse>("/reports", {
    params: { limit },
  });
}

export async function fetchAuditLogs(limit = 5): Promise<AuditListResponse> {
  return api.get<AuditListResponse>("/audit/logs", {
    params: { limit },
  });
}

export async function fetchBatchProcessingStatus(
  tenderId: string,
  versionId: string
): Promise<DocumentBatchStatusResponse> {
  return api.get<DocumentBatchStatusResponse>(
    `/tenders/${tenderId}/versions/${versionId}/processing-status`
  );
}

/**
 * Fetch all dashboard metrics in parallel using resilient Promise.allSettled.
 * If one endpoint fails or lacks permission, the other modules continue to display.
 */
export async function fetchCompleteDashboardData(): Promise<DashboardMetrics> {
  const [
    tendersRes,
    publishedTendersRes,
    draftTendersRes,
    closedTendersRes,
    cancelledTendersRes,
    openReviewsRes,
    inReviewRes,
    resolvedReviewsRes,
    reportsRes,
    auditRes,
  ] = await Promise.allSettled([
    fetchTendersList(1, 10),
    fetchTendersList(1, 1, "PUBLISHED"),
    fetchTendersList(1, 1, "DRAFT"),
    fetchTendersList(1, 1, "CLOSED"),
    fetchTendersList(1, 1, "CANCELLED"),
    fetchReviewCases("OPEN", 10),
    fetchReviewCases("IN_REVIEW", 1),
    fetchReviewCases("RESOLVED", 1),
    fetchReportsList(10),
    fetchAuditLogs(5),
  ]);

  // 1. Process Tenders Metrics
  const tendersMetric = {
    total: 0,
    active: 0,
    draft: 0,
    closed: 0,
    cancelled: 0,
    recent: [] as TenderItem[],
    error: undefined as string | undefined,
  };

  if (tendersRes.status === "fulfilled") {
    tendersMetric.total = tendersRes.value.total;
    tendersMetric.recent = tendersRes.value.items;
  } else {
    tendersMetric.error = tendersRes.reason?.message || "Unable to fetch tenders list.";
  }

  if (publishedTendersRes.status === "fulfilled") {
    tendersMetric.active = publishedTendersRes.value.total;
  }
  if (draftTendersRes.status === "fulfilled") {
    tendersMetric.draft = draftTendersRes.value.total;
  }
  if (closedTendersRes.status === "fulfilled") {
    tendersMetric.closed = closedTendersRes.value.total;
  }
  if (cancelledTendersRes.status === "fulfilled") {
    tendersMetric.cancelled = cancelledTendersRes.value.total;
  }

  // 2. Process Reviews Metrics
  const reviewsMetric = {
    open: 0,
    inReview: 0,
    resolved: 0,
    itemsNeedingAttention: [] as ReviewCaseItem[],
    error: undefined as string | undefined,
  };

  if (openReviewsRes.status === "fulfilled") {
    reviewsMetric.open = openReviewsRes.value.total;
    reviewsMetric.itemsNeedingAttention = openReviewsRes.value.items;
  } else {
    reviewsMetric.error = openReviewsRes.reason?.message || "Unable to fetch review cases.";
  }

  if (inReviewRes.status === "fulfilled") {
    reviewsMetric.inReview = inReviewRes.value.total;
  }
  if (resolvedReviewsRes.status === "fulfilled") {
    reviewsMetric.resolved = resolvedReviewsRes.value.total;
  }

  // 3. Process Reports Metrics
  const reportsMetric = {
    total: 0,
    recent: [] as ReportItem[],
    error: undefined as string | undefined,
  };

  if (reportsRes.status === "fulfilled") {
    reportsMetric.total = reportsRes.value.total;
    reportsMetric.recent = reportsRes.value.items;
  } else {
    reportsMetric.error = reportsRes.reason?.message || "Unable to fetch reports.";
  }

  // 4. Process Audit Logs Metrics
  const auditMetric = {
    total: 0,
    recent: [] as AuditLogItem[],
    error: undefined as string | undefined,
  };

  if (auditRes.status === "fulfilled") {
    auditMetric.total = auditRes.value.total;
    auditMetric.recent = auditRes.value.items;
  } else {
    auditMetric.error = auditRes.reason?.message || "Unable to fetch audit logs.";
  }

  // 5. Process Document Processing Status for most recent tender version
  const processingMetric = {
    available: false,
    total: 0,
    completed: 0,
    processing: 0,
    queued: 0,
    failed: 0,
    failedItems: [] as DocumentBatchItemStatus[],
    error: undefined as string | undefined,
  };

  const latestTender = tendersMetric.recent.length > 0 ? tendersMetric.recent[0] : null;
  const activeVersion = latestTender?.active_version;

  if (latestTender && activeVersion) {
    try {
      const procRes = await fetchBatchProcessingStatus(latestTender.id, activeVersion.id);
      processingMetric.available = true;
      processingMetric.total = procRes.total;
      processingMetric.completed = procRes.completed;
      processingMetric.processing = procRes.processing;
      processingMetric.queued = procRes.queued;
      processingMetric.failed = procRes.failed;
      processingMetric.failedItems = procRes.items.filter((item) => item.status === "FAILED");
    } catch (procErr: unknown) {
      processingMetric.error = (procErr as Error).message || "Could not load document jobs.";
    }
  }

  return {
    tenders: tendersMetric,
    reviews: reviewsMetric,
    reports: reportsMetric,
    processing: processingMetric,
    auditLogs: auditMetric,
    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  };
}
