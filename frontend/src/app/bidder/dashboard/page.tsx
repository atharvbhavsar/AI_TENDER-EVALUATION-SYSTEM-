"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TableSkeleton, Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { getBidderDashboard, type BidderDashboardMetrics } from "@/lib/api/bidder";

function BidderDashboardContent() {
  const [metrics, setMetrics] = useState<BidderDashboardMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    getBidderDashboard()
      .then((data) => {
        if (isMounted) {
          setMetrics(data);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError((err as Error).message || "Failed to load bidder dashboard metrics.");
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title={metrics ? `Welcome, ${metrics.company_name}` : "Bidder Dashboard"}
          description="Manage corporate bid applications, monitor qualification status, and discover open procurement opportunities."
          breadcrumbs={[{ label: "Bidder Portal", href: "/bidder/dashboard" }, { label: "Dashboard" }]}
          actions={
            <Link href="/tenders/public" style={{ textDecoration: "none" }}>
              <Button variant="primary" size="sm" style={{ backgroundColor: "#166534" }}>
                Browse Open Tenders ↗
              </Button>
            </Link>
          }
        />

        {error ? (
          <ErrorState
            title="Failed to Load Dashboard"
            error={error}
            onRetry={() => {
              setIsLoading(true);
              setError(null);
              getBidderDashboard()
                .then(setMetrics)
                .catch((e) => setError((e as Error).message))
                .finally(() => setIsLoading(false));
            }}
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* KPI Metric Summary Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px" }}>
              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-text-muted)", textTransform: "uppercase" }}>
                  My Applications
                </div>
                {isLoading ? (
                  <Skeleton width="40px" height="28px" style={{ marginTop: "6px" }} />
                ) : (
                  <div style={{ fontSize: "26px", fontWeight: 800, color: "var(--gov-primary)", marginTop: "4px" }}>
                    {metrics?.total_applications ?? 0}
                  </div>
                )}
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#475569", textTransform: "uppercase" }}>
                  Draft Proposals
                </div>
                {isLoading ? (
                  <Skeleton width="40px" height="28px" style={{ marginTop: "6px" }} />
                ) : (
                  <div style={{ fontSize: "26px", fontWeight: 800, color: "#475569", marginTop: "4px" }}>
                    {metrics?.draft_count ?? 0}
                  </div>
                )}
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#166534", textTransform: "uppercase" }}>
                  Submitted & Sealed
                </div>
                {isLoading ? (
                  <Skeleton width="40px" height="28px" style={{ marginTop: "6px" }} />
                ) : (
                  <div style={{ fontSize: "26px", fontWeight: 800, color: "#166534", marginTop: "4px" }}>
                    {metrics?.submitted_count ?? 0}
                  </div>
                )}
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#b45309", textTransform: "uppercase" }}>
                  In Review / Processing
                </div>
                {isLoading ? (
                  <Skeleton width="40px" height="28px" style={{ marginTop: "6px" }} />
                ) : (
                  <div style={{ fontSize: "26px", fontWeight: 800, color: "#b45309", marginTop: "4px" }}>
                    {(metrics?.processing_count ?? 0) + (metrics?.review_count ?? 0)}
                  </div>
                )}
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#0284c7", textTransform: "uppercase" }}>
                  Open Tenders
                </div>
                {isLoading ? (
                  <Skeleton width="40px" height="28px" style={{ marginTop: "6px" }} />
                ) : (
                  <div style={{ fontSize: "26px", fontWeight: 800, color: "#0284c7", marginTop: "4px" }}>
                    {metrics?.available_tenders_count ?? 0}
                  </div>
                )}
              </div>
            </div>

            {/* Recent Applications Table */}
            <Card>
              <CardHeader>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <CardTitle style={{ fontSize: "16px" }}>Recent Bid Applications</CardTitle>
                    <CardDescription>Track status, submission references, and specifications for your tenders.</CardDescription>
                  </div>

                  <Link href="/bidder/applications" style={{ textDecoration: "none" }}>
                    <Button variant="outline" size="sm">
                      View All Applications →
                    </Button>
                  </Link>
                </div>
              </CardHeader>

              <CardContent style={{ padding: 0 }}>
                {isLoading ? (
                  <div style={{ padding: "16px" }}>
                    <TableSkeleton rows={3} columns={5} />
                  </div>
                ) : !metrics || metrics.recent_applications.length === 0 ? (
                  <div style={{ padding: "32px 16px" }}>
                    <EmptyState
                      icon="📝"
                      title="No Applications Submitted"
                      description="Your company has not yet applied to any active procurement tenders."
                      action={
                        <Link href="/tenders/public" style={{ textDecoration: "none" }}>
                          <Button variant="primary" size="sm" style={{ backgroundColor: "#166534" }}>
                            Explore Published Tenders
                          </Button>
                        </Link>
                      }
                    />
                  </div>
                ) : (
                  <div style={{ overflowX: "auto" }}>
                    <table className="gov-table" style={{ margin: 0 }}>
                      <thead>
                        <tr>
                          <th>Application Ref</th>
                          <th>Tender Ref & Title</th>
                          <th>Authority</th>
                          <th>Specification</th>
                          <th>Status</th>
                          <th>Applied Date</th>
                          <th style={{ textAlign: "right" }}>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.recent_applications.map((app) => (
                          <tr key={app.id}>
                            <td style={{ fontWeight: 700, color: "var(--gov-primary)", whiteSpace: "nowrap" }}>
                              {app.submission_reference}
                            </td>
                            <td style={{ maxWidth: "280px" }}>
                              <div style={{ fontWeight: 600, color: "var(--gov-text-primary)" }}>
                                {app.tender_number}
                              </div>
                              <div
                                style={{
                                  fontSize: "12px",
                                  color: "var(--gov-text-secondary)",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {app.tender_title}
                              </div>
                            </td>
                            <td style={{ fontSize: "12px", color: "var(--gov-text-secondary)", whiteSpace: "nowrap" }}>
                              {app.issuing_authority}
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
                                v{app.version_number}
                              </span>
                            </td>
                            <td style={{ whiteSpace: "nowrap" }}>
                              <StatusBadge status={app.status} size="sm" />
                            </td>
                            <td style={{ fontSize: "12px", color: "var(--gov-text-muted)", whiteSpace: "nowrap" }}>
                              {new Date(app.created_at).toLocaleDateString("en-IN", {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                              })}
                            </td>
                            <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                              <Link href={`/bidder/applications/${app.id}`} style={{ textDecoration: "none" }}>
                                <Button variant="ghost" size="sm">
                                  View Details →
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
          </div>
        )}
      </PageContainer>
    </AppShell>
  );
}

export default function BidderDashboardPage() {
  return (
    <ProtectedRoute requiredPermission="BIDDER_READ">
      <BidderDashboardContent />
    </ProtectedRoute>
  );
}
