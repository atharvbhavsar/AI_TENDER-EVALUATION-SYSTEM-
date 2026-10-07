"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import {
  listBidderApplications,
  type ApplicationSummaryItem,
  type SubmissionStatus,
} from "@/lib/api/bidder";

function ApplicationsContent() {
  const [applications, setApplications] = useState<ApplicationSummaryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<SubmissionStatus | undefined>(undefined);

  const fetchApplications = useCallback(async (filter?: SubmissionStatus) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await listBidderApplications(1, 50, filter);
      setApplications(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to load your applications.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    listBidderApplications(1, 50)
      .then((res) => {
        if (isMounted) {
          setApplications(res.items);
          setTotal(res.total);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError((err as Error).message || "Failed to load your applications.");
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleFilter = (status?: SubmissionStatus) => {
    setStatusFilter(status);
    fetchApplications(status);
  };

  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="My Bid Applications"
          description={`Viewing ${total} tender proposals registered under your corporate profile.`}
          breadcrumbs={[
            { label: "Bidder Portal", href: "/bidder/dashboard" },
            { label: "My Applications" },
          ]}
          actions={
            <Link href="/tenders/public" style={{ textDecoration: "none" }}>
              <Button variant="primary" size="sm" style={{ backgroundColor: "#166534" }}>
                + Apply for Tender
              </Button>
            </Link>
          }
        />

        {/* Status Filter Tabs */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "20px", flexWrap: "wrap" }}>
          <Button
            variant={statusFilter === undefined ? "primary" : "outline"}
            size="sm"
            onClick={() => handleFilter(undefined)}
          >
            All Applications ({total})
          </Button>
          <Button
            variant={statusFilter === "DRAFT" ? "primary" : "outline"}
            size="sm"
            onClick={() => handleFilter("DRAFT")}
          >
            Draft
          </Button>
          <Button
            variant={statusFilter === "SUBMITTED" ? "primary" : "outline"}
            size="sm"
            onClick={() => handleFilter("SUBMITTED")}
          >
            Submitted
          </Button>
          <Button
            variant={statusFilter === "RECEIVED" ? "primary" : "outline"}
            size="sm"
            onClick={() => handleFilter("RECEIVED")}
          >
            Received
          </Button>
          <Button
            variant={statusFilter === "PROCESSING" ? "primary" : "outline"}
            size="sm"
            onClick={() => handleFilter("PROCESSING")}
          >
            Processing
          </Button>
          <Button
            variant={statusFilter === "READY" ? "primary" : "outline"}
            size="sm"
            onClick={() => handleFilter("READY")}
          >
            Ready
          </Button>
          <Button
            variant={statusFilter === "REVIEW" ? "primary" : "outline"}
            size="sm"
            onClick={() => handleFilter("REVIEW")}
          >
            Review
          </Button>
        </div>

        {/* Applications List Table */}
        <Card>
          <CardHeader>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <CardTitle style={{ fontSize: "16px" }}>Registered Submissions Repository</CardTitle>
                <CardDescription>
                  Click on any application to view requirement checklists and tender specifications.
                </CardDescription>
              </div>
              <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                Showing {applications.length} of {total}
              </span>
            </div>
          </CardHeader>

          <CardContent style={{ padding: 0 }}>
            {isLoading ? (
              <div style={{ padding: "16px" }}>
                <TableSkeleton rows={4} columns={6} />
              </div>
            ) : error ? (
              <div style={{ padding: "20px" }}>
                <ErrorState
                  title="Failed to Load Applications"
                  error={error}
                  onRetry={() => fetchApplications(statusFilter)}
                />
              </div>
            ) : applications.length === 0 ? (
              <div style={{ padding: "32px 16px" }}>
                <EmptyState
                  icon="📋"
                  title="No Applications Found"
                  description={
                    statusFilter
                      ? `No applications currently have status "${statusFilter}".`
                      : "Your company has not yet submitted applications to any tender."
                  }
                  action={
                    <Link href="/tenders/public" style={{ textDecoration: "none" }}>
                      <Button variant="primary" size="sm" style={{ backgroundColor: "#166534" }}>
                        Browse Active Tenders
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
                      <th>Submission Reference</th>
                      <th>Tender Notice</th>
                      <th>Authority</th>
                      <th>Version</th>
                      <th>Lifecycle</th>
                      <th>Registered</th>
                      <th style={{ textAlign: "right" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applications.map((app) => (
                      <tr key={app.id}>
                        <td style={{ fontWeight: 700, color: "var(--gov-primary)", whiteSpace: "nowrap" }}>
                          {app.submission_reference}
                        </td>
                        <td style={{ maxWidth: "260px" }}>
                          <div style={{ fontWeight: 600, color: "var(--gov-text-primary)" }}>
                            {app.tender_number}
                          </div>
                          <div
                            style={{
                              fontSize: "11px",
                              color: "var(--gov-text-muted)",
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
      </PageContainer>
    </AppShell>
  );
}

export default function BidderApplicationsPage() {
  return (
    <ProtectedRoute requiredPermission="BIDDER_READ">
      <ApplicationsContent />
    </ProtectedRoute>
  );
}
