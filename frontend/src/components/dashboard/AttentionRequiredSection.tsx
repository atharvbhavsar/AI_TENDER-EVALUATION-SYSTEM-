import React from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ReviewCaseItem, DocumentBatchItemStatus } from "@/lib/api/dashboard";

export interface AttentionRequiredProps {
  reviewCases: ReviewCaseItem[];
  failedJobs: DocumentBatchItemStatus[];
  isLoading?: boolean;
  error?: string;
}

export function AttentionRequiredSection({
  reviewCases,
  failedJobs,
  isLoading = false,
  error,
}: AttentionRequiredProps) {
  const totalIssues = reviewCases.length + failedJobs.length;

  return (
    <Card style={{ borderLeft: totalIssues > 0 ? "4px solid var(--gov-gold)" : "4px solid #22c55e" }}>
      <CardHeader>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <CardTitle>Attention Required</CardTitle>
              {!isLoading && (
                <span
                  style={{
                    backgroundColor: totalIssues > 0 ? "#fef3c7" : "#dcfce7",
                    color: totalIssues > 0 ? "#92400e" : "#166534",
                    border: `1px solid ${totalIssues > 0 ? "#fcd34d" : "#86efac"}`,
                    fontSize: "11px",
                    fontWeight: 700,
                    padding: "1px 7px",
                    borderRadius: "10px",
                  }}
                >
                  {totalIssues} {totalIssues === 1 ? "Item" : "Items"}
                </span>
              )}
            </div>
            <CardDescription>
              Officer review queues, ambiguous citations, and document processing exception flags.
            </CardDescription>
          </div>

          <Link href="/reviews" style={{ textDecoration: "none" }}>
            <Button variant="outline" size="sm">
              Open Review Queue →
            </Button>
          </Link>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <Skeleton width="100%" height="56px" />
            <Skeleton width="100%" height="56px" />
          </div>
        ) : error ? (
          <div style={{ fontSize: "12px", color: "var(--status-danger-text)" }}>
            Unable to query review queues: {error}
          </div>
        ) : totalIssues === 0 ? (
          <div
            style={{
              padding: "24px 16px",
              textAlign: "center",
              backgroundColor: "var(--status-success-bg)",
              border: "1px solid var(--status-success-border)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <div style={{ fontSize: "20px", marginBottom: "6px" }}>✓</div>
            <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--status-success-text)" }}>
              No Pending Action Items
            </div>
            <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
              All submitted documents and evaluation rules have been evaluated without exceptions.
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {/* Failed Document Processing Jobs */}
            {failedJobs.map((job) => (
              <div
                key={job.document_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  backgroundColor: "var(--status-danger-bg)",
                  border: "1px solid var(--status-danger-border)",
                  borderRadius: "var(--radius-md)",
                  gap: "12px",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--status-danger-text)" }}>
                      Processing Failure: {job.filename}
                    </span>
                    <StatusBadge status="FAILED" size="sm" />
                  </div>
                  <div style={{ fontSize: "11px", color: "#7f1d1d", marginTop: "2px" }}>
                    Error code: {job.error_code || "DOCUMENT_INGESTION_ERROR"} • Attempt {job.attempt_count}/3
                  </div>
                </div>

                <Link href="/tenders" style={{ textDecoration: "none" }}>
                  <Button variant="outline" size="sm">
                    Inspect Ingestion
                  </Button>
                </Link>
              </div>
            ))}

            {/* Review Cases */}
            {reviewCases.map((rc) => (
              <div
                key={rc.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  backgroundColor: "var(--gov-surface-secondary)",
                  border: "1px solid var(--gov-border)",
                  borderRadius: "var(--radius-md)",
                  gap: "12px",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 700,
                        padding: "1px 6px",
                        borderRadius: "3px",
                        backgroundColor:
                          rc.priority === "CRITICAL"
                            ? "#fee2e2"
                            : rc.priority === "HIGH"
                            ? "#fef3c7"
                            : "#e0f2fe",
                        color:
                          rc.priority === "CRITICAL"
                            ? "#991b1b"
                            : rc.priority === "HIGH"
                            ? "#92400e"
                            : "#0369a1",
                      }}
                    >
                      {rc.priority} PRIORITY
                    </span>
                    <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--gov-text-primary)" }}>
                      {rc.title}
                    </span>
                  </div>

                  <div
                    style={{
                      fontSize: "11px",
                      color: "var(--gov-text-muted)",
                      marginTop: "3px",
                      display: "flex",
                      gap: "12px",
                    }}
                  >
                    <span>Issue: {rc.issue_type.replace(/_/g, " ")}</span>
                    <span>Created: {new Date(rc.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                <Link href={`/reviews`} style={{ textDecoration: "none" }}>
                  <Button variant="secondary" size="sm">
                    Review Case →
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
