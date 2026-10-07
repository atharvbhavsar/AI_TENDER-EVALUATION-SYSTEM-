import React from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Skeleton } from "@/components/ui/Skeleton";

export interface StatusDistributionProps {
  tenders: {
    total: number;
    active: number;
    draft: number;
    closed: number;
    cancelled: number;
    error?: string;
  };
  isLoading?: boolean;
}

export function StatusDistributionCard({ tenders, isLoading = false }: StatusDistributionProps) {
  const statuses = [
    { label: "Active (Published)", count: tenders.active, status: "PUBLISHED" as const, desc: "Open for bidder submissions" },
    { label: "Draft (Pending)", count: tenders.draft, status: "DRAFT" as const, desc: "Under specification preparation" },
    { label: "Closed", count: tenders.closed, status: "CLOSED" as const, desc: "Bidding window concluded" },
    { label: "Cancelled", count: tenders.cancelled, status: "CANCELLED" as const, desc: "Revoked or superseded" },
  ];

  return (
    <Card>
      <CardHeader>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <CardTitle>Tender Status Distribution</CardTitle>
            <CardDescription>Real-time lifecycle breakdown across all procurement notices.</CardDescription>
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
            {isLoading ? <Skeleton width="30px" height="14px" /> : `${tenders.total} Total`}
          </span>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <Skeleton width="100%" height="32px" />
            <Skeleton width="100%" height="32px" />
            <Skeleton width="100%" height="32px" />
          </div>
        ) : tenders.error ? (
          <div style={{ fontSize: "12px", color: "var(--status-danger-text)" }}>
            Failed to load status breakdown: {tenders.error}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {statuses.map((item) => (
              <div
                key={item.status}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "var(--gov-surface-secondary)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <StatusBadge status={item.status} size="sm" />
                  <span style={{ fontSize: "12px", fontWeight: 500, color: "var(--gov-text-secondary)" }}>
                    {item.label}
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "14px", fontWeight: 700, color: "var(--gov-text-primary)" }}>
                    {item.count}
                  </span>
                  {tenders.total > 0 && (
                    <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                      ({Math.round((item.count / tenders.total) * 100)}%)
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
