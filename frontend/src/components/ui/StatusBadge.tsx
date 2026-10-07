import React from "react";
import type {
  EvaluationResult,
  EvidenceStatus,
  ProcessingStatus,
  RankingStatus,
  ReviewStatus,
  SubmissionStatus,
  TenderStatus,
} from "@/types/status";

export type AnyBackendStatus =
  | EvaluationResult
  | EvidenceStatus
  | ProcessingStatus
  | TenderStatus
  | SubmissionStatus
  | RankingStatus
  | ReviewStatus
  | string;

interface StatusConfig {
  label: string;
  symbol: string;
  bg: string;
  text: string;
  border: string;
}

const STATUS_CONFIGS: Record<string, StatusConfig> = {
  // Evaluation Outcomes
  ELIGIBLE: {
    label: "ELIGIBLE",
    symbol: "✓",
    bg: "var(--status-success-bg)",
    text: "var(--status-success-text)",
    border: "var(--status-success-border)",
  },
  NOT_ELIGIBLE: {
    label: "NOT ELIGIBLE",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },
  MANUAL_REVIEW: {
    label: "MANUAL REVIEW",
    symbol: "⚠",
    bg: "var(--status-warning-bg)",
    text: "var(--status-warning-text)",
    border: "var(--status-warning-border)",
  },

  // Evidence Statuses
  FOUND: {
    label: "FOUND",
    symbol: "✓",
    bg: "var(--status-success-bg)",
    text: "var(--status-success-text)",
    border: "var(--status-success-border)",
  },
  MISSING: {
    label: "MISSING",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },
  UNREADABLE: {
    label: "UNREADABLE",
    symbol: "👁",
    bg: "var(--status-warning-bg)",
    text: "var(--status-warning-text)",
    border: "var(--status-warning-border)",
  },
  CONFLICTING: {
    label: "CONFLICTING",
    symbol: "⚡",
    bg: "var(--status-warning-bg)",
    text: "var(--status-warning-text)",
    border: "var(--status-warning-border)",
  },
  AMBIGUOUS: {
    label: "AMBIGUOUS",
    symbol: "?",
    bg: "var(--status-warning-bg)",
    text: "var(--status-warning-text)",
    border: "var(--status-warning-border)",
  },
  INVALID: {
    label: "INVALID",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },

  // Document & Job Processing Statuses
  UPLOADED: {
    label: "UPLOADED",
    symbol: "↑",
    bg: "var(--status-neutral-bg)",
    text: "var(--status-neutral-text)",
    border: "var(--status-neutral-border)",
  },
  VALIDATING: {
    label: "VALIDATING",
    symbol: "◌",
    bg: "var(--status-info-bg)",
    text: "var(--status-info-text)",
    border: "var(--status-info-border)",
  },
  VALIDATED: {
    label: "VALIDATED",
    symbol: "✓",
    bg: "var(--status-success-bg)",
    text: "var(--status-success-text)",
    border: "var(--status-success-border)",
  },
  REJECTED: {
    label: "REJECTED",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },
  PROCESSING: {
    label: "PROCESSING",
    symbol: "◌",
    bg: "var(--status-info-bg)",
    text: "var(--status-info-text)",
    border: "var(--status-info-border)",
  },
  COMPLETED: {
    label: "COMPLETED",
    symbol: "✓",
    bg: "var(--status-success-bg)",
    text: "var(--status-success-text)",
    border: "var(--status-success-border)",
  },
  FAILED: {
    label: "FAILED",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },

  // Tender Lifecycle Statuses
  DRAFT: {
    label: "DRAFT",
    symbol: "✎",
    bg: "var(--status-neutral-bg)",
    text: "var(--status-neutral-text)",
    border: "var(--status-neutral-border)",
  },
  PUBLISHED: {
    label: "PUBLISHED",
    symbol: "●",
    bg: "var(--status-success-bg)",
    text: "var(--status-success-text)",
    border: "var(--status-success-border)",
  },
  CLOSED: {
    label: "CLOSED",
    symbol: "■",
    bg: "var(--status-neutral-bg)",
    text: "var(--status-neutral-text)",
    border: "var(--status-neutral-border)",
  },
  CANCELLED: {
    label: "CANCELLED",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },

  // Submission Statuses
  SUBMITTED: {
    label: "SUBMITTED",
    symbol: "✓",
    bg: "#ecfdf5",
    text: "#065f46",
    border: "#a7f3d0",
  },
  RECEIVED: {
    label: "RECEIVED",
    symbol: "📥",
    bg: "var(--status-info-bg)",
    text: "var(--status-info-text)",
    border: "var(--status-info-border)",
  },
  READY: {
    label: "READY",
    symbol: "✓",
    bg: "var(--status-success-bg)",
    text: "var(--status-success-text)",
    border: "var(--status-success-border)",
  },
  REVIEW: {
    label: "IN REVIEW",
    symbol: "⚠",
    bg: "var(--status-warning-bg)",
    text: "var(--status-warning-text)",
    border: "var(--status-warning-border)",
  },

  // Ranking Statuses
  QUALIFIED_RANKED: {
    label: "QUALIFIED (RANKED)",
    symbol: "★",
    bg: "var(--status-success-bg)",
    text: "var(--status-success-text)",
    border: "var(--status-success-border)",
  },
  EXCLUDED_INELIGIBLE: {
    label: "EXCLUDED (INELIGIBLE)",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },
  PENDING_MANUAL_REVIEW: {
    label: "PENDING REVIEW",
    symbol: "⚠",
    bg: "var(--status-warning-bg)",
    text: "var(--status-warning-text)",
    border: "var(--status-warning-border)",
  },
  TIE_REQUIRES_HUMAN_REVIEW: {
    label: "TIE (REQUIRES REVIEW)",
    symbol: "⚠",
    bg: "var(--status-warning-bg)",
    text: "var(--status-warning-text)",
    border: "var(--status-warning-border)",
  },
  MISSING_FINANCIAL_BID: {
    label: "MISSING PRICE",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },
  DISQUALIFIED_TECHNICAL: {
    label: "DISQUALIFIED (TECH)",
    symbol: "✕",
    bg: "var(--status-danger-bg)",
    text: "var(--status-danger-text)",
    border: "var(--status-danger-border)",
  },

  // Review Case Statuses
  OPEN: {
    label: "OPEN",
    symbol: "●",
    bg: "var(--status-warning-bg)",
    text: "var(--status-warning-text)",
    border: "var(--status-warning-border)",
  },
  IN_REVIEW: {
    label: "IN REVIEW",
    symbol: "◌",
    bg: "var(--status-info-bg)",
    text: "var(--status-info-text)",
    border: "var(--status-info-border)",
  },
  RESOLVED: {
    label: "RESOLVED",
    symbol: "✓",
    bg: "var(--status-success-bg)",
    text: "var(--status-success-text)",
    border: "var(--status-success-border)",
  },
};

export interface StatusBadgeProps {
  status: AnyBackendStatus;
  size?: "sm" | "md";
  className?: string;
  showSymbol?: boolean;
}

export function StatusBadge({
  status,
  size = "md",
  className = "",
  showSymbol = true,
}: StatusBadgeProps) {
  const key = String(status || "").toUpperCase();
  const config = STATUS_CONFIGS[key] || {
    label: key || "UNKNOWN",
    symbol: "•",
    bg: "var(--status-neutral-bg)",
    text: "var(--status-neutral-text)",
    border: "var(--status-neutral-border)",
  };

  const isSmall = size === "sm";

  return (
    <span
      role="status"
      aria-label={`Status: ${config.label}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: isSmall ? "2px 6px" : "3px 8px",
        fontSize: isSmall ? "11px" : "12px",
        fontWeight: 600,
        borderRadius: "4px",
        backgroundColor: config.bg,
        color: config.text,
        border: `1px solid ${config.border}`,
        lineHeight: 1.2,
        letterSpacing: "0.02em",
        whiteSpace: "nowrap",
        userSelect: "none",
      }}
      className={className}
    >
      {showSymbol && (
        <span aria-hidden="true" style={{ fontWeight: 700, fontSize: "11px" }}>
          {config.symbol}
        </span>
      )}
      <span>{config.label}</span>
    </span>
  );
}
