/**
 * Controlled status enums mirroring FastAPI backend PostgreSQL database models exactly.
 * DO NOT invent or modify status values here without corresponding backend model changes.
 */

// Phase 10: Controlled Evidence Extraction & Validation Status
export type EvidenceStatus =
  | "FOUND"
  | "MISSING"
  | "UNREADABLE"
  | "CONFLICTING"
  | "AMBIGUOUS"
  | "INVALID";

// Phase 11 & 21: Deterministic Criterion & Bidder Evaluation Outcome
export type EvaluationResult =
  | "ELIGIBLE"
  | "NOT_ELIGIBLE"
  | "MANUAL_REVIEW";

// Phase 4: Document Ingestion and Processing Status
export type ProcessingStatus =
  | "UPLOADED"
  | "VALIDATING"
  | "VALIDATED"
  | "REJECTED"
  | "PROCESSING"
  | "COMPLETED"
  | "FAILED";

// Phase 2: Controlled Tender Lifecycle Statuses
export type TenderStatus =
  | "DRAFT"
  | "PUBLISHED"
  | "CLOSED"
  | "CANCELLED";

// Phase 5 & 8: Controlled Bidder Submission Statuses
export type SubmissionStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "RECEIVED"
  | "PROCESSING"
  | "READY"
  | "REVIEW";

// Phase 21: Comparative Ranking Status
export type RankingStatus =
  | "QUALIFIED_RANKED"
  | "EXCLUDED_INELIGIBLE"
  | "PENDING_MANUAL_REVIEW"
  | "TIE_REQUIRES_HUMAN_REVIEW"
  | "MISSING_FINANCIAL_BID"
  | "DISQUALIFIED_TECHNICAL";

// Phase 14: Human Review Case Statuses
export type ReviewStatus =
  | "OPEN"
  | "IN_REVIEW"
  | "RESOLVED";

export type ReviewPriority =
  | "LOW"
  | "MEDIUM"
  | "HIGH"
  | "CRITICAL";

export type ReviewIssueType =
  | "MANUAL_REVIEW_REQUIRED"
  | "MISSING_EVIDENCE"
  | "AMBIGUOUS_EVIDENCE"
  | "CONFLICTING_EVIDENCE"
  | "UNREADABLE_EVIDENCE"
  | "INVALID_EVIDENCE"
  | "UNSUPPORTED_RULE";

export type HumanDecision =
  | "ACCEPT"
  | "REJECT"
  | "OVERRIDE"
  | "REQUEST_MORE_INFO";

// Phase 16: Evaluation Report Status
export type ReportStatus =
  | "GENERATING"
  | "COMPLETED"
  | "FAILED";

export type ReportType =
  | "TECHNICAL_EVALUATION"
  | "COMPARATIVE_RANKING"
  | "BIDDER_SUMMARY"
  | "AUDIT_REPORT";
