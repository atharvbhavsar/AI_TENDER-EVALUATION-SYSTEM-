import React from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import type { TenderItem } from "@/lib/api/dashboard";

export interface RecentTendersTableProps {
  tenders: TenderItem[];
  totalCount: number;
  isLoading?: boolean;
  error?: string;
  onRetry?: () => void;
}

export function RecentTendersTable({
  tenders,
  totalCount,
  isLoading = false,
  error,
  onRetry,
}: RecentTendersTableProps) {
  return (
    <Card>
      <CardHeader>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
          <div>
            <CardTitle>Recent Procurement Tenders</CardTitle>
            <CardDescription>Active and drafted tender notices recorded in the central repository.</CardDescription>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Link href="/tenders" style={{ textDecoration: "none" }}>
              <Button variant="outline" size="sm">
                View All Tenders ({totalCount}) →
              </Button>
            </Link>
          </div>
        </div>
      </CardHeader>

      <CardContent style={{ padding: 0 }}>
        {isLoading ? (
          <div style={{ padding: "16px" }}>
            <TableSkeleton rows={4} columns={6} />
          </div>
        ) : error ? (
          <div style={{ padding: "24px 16px", textAlign: "center" }}>
            <div style={{ color: "var(--status-danger-text)", fontSize: "13px", marginBottom: "8px" }}>
              {error}
            </div>
            {onRetry && (
              <Button variant="outline" size="sm" onClick={onRetry}>
                Retry Loading
              </Button>
            )}
          </div>
        ) : tenders.length === 0 ? (
          <div style={{ padding: "32px 16px" }}>
            <EmptyState
              icon="📋"
              title="No Tenders Found"
              description="There are currently no procurement tenders registered in the backend database."
              action={
                <Link href="/tenders" style={{ textDecoration: "none" }}>
                  <Button variant="primary" size="sm">
                    Go to Tenders Module
                  </Button>
                </Link>
              }
            />
          </div>
        ) : (
          <div style={{ overflowX: "auto", width: "100%" }}>
            <table className="gov-table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>Tender Ref No.</th>
                  <th>Title & Description</th>
                  <th>Authority</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {tenders.map((t) => (
                  <tr key={t.id}>
                    <td style={{ fontWeight: 700, color: "var(--gov-primary)", whiteSpace: "nowrap" }}>
                      {t.tender_number}
                    </td>
                    <td style={{ maxWidth: "300px" }}>
                      <div style={{ fontWeight: 600, color: "var(--gov-text-primary)" }}>{t.title}</div>
                      {t.description && (
                        <div
                          style={{
                            fontSize: "11px",
                            color: "var(--gov-text-muted)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {t.description}
                        </div>
                      )}
                    </td>
                    <td style={{ fontSize: "12px", color: "var(--gov-text-secondary)", whiteSpace: "nowrap" }}>
                      {t.issuing_authority}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          backgroundColor: "var(--gov-surface-secondary)",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          color: "var(--gov-text-secondary)",
                        }}
                      >
                        v{t.active_version ? t.active_version.version_number : 1}
                      </span>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <StatusBadge status={t.status} size="sm" />
                    </td>
                    <td style={{ fontSize: "12px", color: "var(--gov-text-muted)", whiteSpace: "nowrap" }}>
                      {new Date(t.created_at).toLocaleDateString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })}
                    </td>
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      <Link href="/tenders" style={{ textDecoration: "none" }}>
                        <Button variant="ghost" size="sm">
                          View →
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
