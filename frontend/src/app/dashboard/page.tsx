"use client";

import React, { useState, useEffect, useCallback } from "react";
import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { ErrorState } from "@/components/ui/ErrorState";
import { BackendHealthCard } from "@/components/diagnostics/BackendHealthCard";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api/client";
import {
  fetchCompleteDashboardData,
  type DashboardMetrics,
} from "@/lib/api/dashboard";
import {
  SummaryCard,
  StatusDistributionCard,
  AttentionRequiredSection,
  RecentTendersTable,
  DocumentProcessingCard,
  RecentActivityCard,
} from "@/components/dashboard";

function DashboardContent() {
  const { currentUser, hasAnyPermission } = useAuth();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // RBAC test state for officer credential verification
  const [adminTestResult, setAdminTestResult] = useState<{ success: boolean; message: string; code?: number } | null>(null);
  const [isAdminTesting, setIsAdminTesting] = useState(false);

  const loadData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setIsRefreshing(true);
    }
    setGlobalError(null);

    try {
      const data = await fetchCompleteDashboardData();
      setMetrics(data);
    } catch (err: unknown) {
      const msg = (err as Error)?.message || "Failed to load dashboard data from backend.";
      setGlobalError(msg);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    fetchCompleteDashboardData()
      .then((data) => {
        if (isMounted) {
          setMetrics(data);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          const msg = (err as Error)?.message || "Failed to load dashboard data from backend.";
          setGlobalError(msg);
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleTestAdminAuthorization = async () => {
    setIsAdminTesting(true);
    setAdminTestResult(null);
    try {
      const res = await api.get<{ status: string; message: string; user: string }>("/auth/admin-test");
      setAdminTestResult({
        success: true,
        message: `${res.message} for ${res.user}`,
        code: 200,
      });
    } catch (err: unknown) {
      if (err && typeof err === "object" && "info" in err) {
        const info = (err as { info: { statusCode?: number; message?: string } }).info;
        setAdminTestResult({
          success: false,
          message:
            info.statusCode === 403
              ? "HTTP 403 Forbidden: You do not possess the required USER_MANAGE administrative permission to access this endpoint."
              : info.message || "Request failed.",
          code: info.statusCode,
        });
      } else {
        setAdminTestResult({
          success: false,
          message: "Request failed to verify admin permissions.",
        });
      }
    } finally {
      setIsAdminTesting(false);
    }
  };

  const canViewAudit = hasAnyPermission(["AUDIT_READ", "REPORT_READ", "EVALUATION_READ"]);

  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="Procurement & Evaluation Dashboard"
          description="Live operational command center for active tenders, evidence extraction queues, OPA evaluations, and audit records."
          breadcrumbs={[{ label: "Dashboard" }]}
          actions={
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              {metrics?.timestamp && (
                <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                  Last synced: {metrics.timestamp}
                </span>
              )}
              <Button
                variant="outline"
                size="sm"
                isLoading={isRefreshing}
                onClick={() => loadData(true)}
              >
                ↻ Refresh Data
              </Button>
            </div>
          }
        />

        {globalError ? (
          <div style={{ marginBottom: "24px" }}>
            <ErrorState
              title="Dashboard Synchronization Failure"
              error={globalError}
              onRetry={() => loadData(false)}
            />
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {/* Top Row: Summary Statistic Cards */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "16px",
              }}
            >
              <SummaryCard
                title="Total Tenders"
                value={metrics?.tenders.total}
                subtitle="All procurement notices"
                icon="📋"
                isLoading={isLoading}
                error={metrics?.tenders.error}
                accentColor="var(--gov-primary)"
              />

              <SummaryCard
                title="Active Tenders"
                value={metrics?.tenders.active}
                subtitle="Published & accepting bids"
                icon="🟢"
                isLoading={isLoading}
                accentColor="#166534"
              />

              <SummaryCard
                title="Pending Tenders"
                value={metrics?.tenders.draft}
                subtitle="Draft specification stage"
                icon="📝"
                isLoading={isLoading}
                accentColor="#92400e"
              />

              <SummaryCard
                title="Manual Reviews"
                value={metrics?.reviews.open}
                subtitle="Officer review required"
                icon="🔍"
                isLoading={isLoading}
                error={metrics?.reviews.error}
                accentColor="#ea580c"
              />

              <SummaryCard
                title="Formal Reports"
                value={metrics?.reports.total}
                subtitle="Completed audit reports"
                icon="📊"
                isLoading={isLoading}
                error={metrics?.reports.error}
                accentColor="#6b21a8"
              />
            </div>

            {/* Attention Required Section: Reviews & Processing Failures */}
            <AttentionRequiredSection
              reviewCases={metrics?.reviews.itemsNeedingAttention || []}
              failedJobs={metrics?.processing.failedItems || []}
              isLoading={isLoading}
              error={metrics?.reviews.error}
            />

            {/* Middle Row: Status Distribution & Document Ingestion Status */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
                gap: "16px",
              }}
            >
              <StatusDistributionCard
                tenders={
                  metrics?.tenders || {
                    total: 0,
                    active: 0,
                    draft: 0,
                    closed: 0,
                    cancelled: 0,
                  }
                }
                isLoading={isLoading}
              />

              <DocumentProcessingCard
                processing={
                  metrics?.processing || {
                    available: false,
                    total: 0,
                    completed: 0,
                    processing: 0,
                    queued: 0,
                    failed: 0,
                  }
                }
                isLoading={isLoading}
              />
            </div>

            {/* Recent Tenders Table */}
            <RecentTendersTable
              tenders={metrics?.tenders.recent || []}
              totalCount={metrics?.tenders.total || 0}
              isLoading={isLoading}
              error={metrics?.tenders.error}
              onRetry={() => loadData(false)}
            />

            {/* Role-Aware Recent Activity / Audit Log Section */}
            {canViewAudit && (
              <RecentActivityCard
                logs={metrics?.auditLogs.recent || []}
                totalLogs={metrics?.auditLogs.total || 0}
                isLoading={isLoading}
                error={metrics?.auditLogs.error}
              />
            )}

            {/* Authenticated Officer Session & Clearance Verification */}
            {currentUser && (
              <Card>
                <CardHeader>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "12px",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                        <CardTitle>{currentUser.full_name}</CardTitle>
                        {currentUser.roles.map((r) => (
                          <span
                            key={r}
                            style={{
                              backgroundColor: "var(--status-info-bg)",
                              color: "var(--status-info-text)",
                              border: "1px solid var(--status-info-border)",
                              fontWeight: 700,
                              padding: "2px 8px",
                              borderRadius: "4px",
                              fontSize: "11px",
                            }}
                          >
                            {r.replace(/_/g, " ")}
                          </span>
                        ))}
                      </div>
                      <CardDescription>
                        Authenticated Official ({currentUser.email}) • {currentUser.permissions.length} permissions active
                      </CardDescription>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Button
                        variant="outline"
                        size="sm"
                        isLoading={isAdminTesting}
                        onClick={handleTestAdminAuthorization}
                      >
                        Verify Admin Clearance (RBAC Test)
                      </Button>
                    </div>
                  </div>
                </CardHeader>

                {adminTestResult && (
                  <CardContent style={{ paddingTop: 0 }}>
                    <Alert
                      variant={adminTestResult.success ? "success" : "danger"}
                      title={
                        adminTestResult.success
                          ? "Authorization Granted (HTTP 200)"
                          : `Access Denied (HTTP ${adminTestResult.code || 403})`
                      }
                    >
                      <p style={{ margin: 0 }}>{adminTestResult.message}</p>
                    </Alert>
                  </CardContent>
                )}
              </Card>
            )}

            {/* Diagnostic Backend Health Connectivity Check */}
            <BackendHealthCard />
          </div>
        )}
      </PageContainer>
    </AppShell>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
