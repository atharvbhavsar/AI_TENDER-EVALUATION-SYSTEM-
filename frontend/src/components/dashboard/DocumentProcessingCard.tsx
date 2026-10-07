import React from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";

export interface DocumentProcessingProps {
  processing: {
    available: boolean;
    total: number;
    completed: number;
    processing: number;
    queued: number;
    failed: number;
    error?: string;
  };
  isLoading?: boolean;
}

export function DocumentProcessingCard({ processing, isLoading = false }: DocumentProcessingProps) {
  const jobStats = [
    { label: "Completed", count: processing.completed, status: "COMPLETED" as const },
    { label: "Processing", count: processing.processing, status: "PROCESSING" as const },
    { label: "Queued", count: processing.queued, status: "UPLOADED" as const },
    { label: "Failed", count: processing.failed, status: "FAILED" as const },
  ];

  return (
    <Card>
      <CardHeader>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <CardTitle>Document Ingestion & OCR</CardTitle>
            <CardDescription>Asynchronous pipeline job execution on Celery/Redis workers.</CardDescription>
          </div>
          <span
            style={{
              fontSize: "11px",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: "10px",
              backgroundColor: "var(--gov-surface-secondary)",
              color: "var(--gov-text-secondary)",
            }}
          >
            {isLoading ? <Skeleton width="30px" height="14px" /> : `${processing.total} Docs`}
          </span>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <Skeleton width="100%" height="28px" />
            <Skeleton width="100%" height="28px" />
            <Skeleton width="100%" height="28px" />
          </div>
        ) : processing.error ? (
          <div style={{ fontSize: "12px", color: "var(--status-danger-text)" }}>
            Unable to load pipeline metrics: {processing.error}
          </div>
        ) : !processing.available && processing.total === 0 ? (
          <div
            style={{
              padding: "20px 12px",
              textAlign: "center",
              backgroundColor: "var(--gov-surface-secondary)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <div style={{ fontSize: "12px", color: "var(--gov-text-secondary)", fontWeight: 500 }}>
              No active document batches
            </div>
            <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
              Upload tender or bidder proposal documents to initialize ingestion jobs.
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            {jobStats.map((stat) => (
              <div
                key={stat.label}
                style={{
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "var(--gov-surface-secondary)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "11px", color: "var(--gov-text-muted)", fontWeight: 600 }}>
                    {stat.label}
                  </span>
                  <StatusBadge status={stat.status} size="sm" />
                </div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--gov-text-primary)" }}>
                  {stat.count}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
