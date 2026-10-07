import React from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import type { AuditLogItem } from "@/lib/api/dashboard";

export interface RecentActivityProps {
  logs: AuditLogItem[];
  totalLogs: number;
  isLoading?: boolean;
  error?: string;
}

export function RecentActivityCard({ logs, totalLogs, isLoading = false, error }: RecentActivityProps) {
  return (
    <Card>
      <CardHeader>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
          <div>
            <CardTitle>Recent System Activity & Audit Trail</CardTitle>
            <CardDescription>Append-only provenance and governance actions recorded by the platform.</CardDescription>
          </div>

          <Link href="/audit" style={{ textDecoration: "none" }}>
            <Button variant="ghost" size="sm">
              Full Audit Log ({totalLogs}) →
            </Button>
          </Link>
        </div>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <Skeleton width="100%" height="32px" />
            <Skeleton width="100%" height="32px" />
            <Skeleton width="100%" height="32px" />
          </div>
        ) : error ? (
          <div style={{ fontSize: "12px", color: "var(--status-danger-text)" }}>
            Unable to load audit activity: {error}
          </div>
        ) : logs.length === 0 ? (
          <div
            style={{
              padding: "24px 16px",
              textAlign: "center",
              backgroundColor: "var(--gov-surface-secondary)",
              borderRadius: "var(--radius-md)",
              fontSize: "12px",
              color: "var(--gov-text-muted)",
            }}
          >
            No audit events recorded in this cycle.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {logs.map((log) => (
              <div
                key={log.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "var(--gov-surface-secondary)",
                  fontSize: "12px",
                  gap: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      backgroundColor: "var(--gov-primary)",
                      flexShrink: 0,
                    }}
                    aria-hidden="true"
                  />
                  <div>
                    <span style={{ fontWeight: 600, color: "var(--gov-text-primary)" }}>
                      {log.action.replace(/_/g, " ")}
                    </span>
                    <span style={{ color: "var(--gov-text-muted)", marginLeft: "6px" }}>
                      ({log.entity_type})
                    </span>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "12px", flexShrink: 0 }}>
                  {log.actor_role && (
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 700,
                        backgroundColor: "var(--status-info-bg)",
                        color: "var(--status-info-text)",
                        padding: "1px 6px",
                        borderRadius: "3px",
                      }}
                    >
                      {log.actor_role}
                    </span>
                  )}
                  <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                    {new Date(log.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
