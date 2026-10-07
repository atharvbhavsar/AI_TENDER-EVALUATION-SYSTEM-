"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Alert } from "@/components/ui/Alert";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";
import {
  listTenders,
  publishTender,
  type TenderItem,
} from "@/lib/api/tenders";
import {
  PublishTenderModal,
  PublicTenderShareBox,
  CreateTenderModal,
} from "@/components/tenders";

function OfficerTendersContent() {
  const { hasPermission } = useAuth();
  const [tenders, setTenders] = useState<TenderItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  // Modals & Active state
  const [selectedTender, setSelectedTender] = useState<TenderItem | null>(null);
  const [publishingTender, setPublishingTender] = useState<TenderItem | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [notification, setNotification] = useState<{ type: "success" | "info"; message: string } | null>(null);

  const canPublish = hasPermission("TENDER_UPDATE");
  const canCreate = hasPermission("TENDER_CREATE");

  const loadTenders = useCallback(async (search?: string, status?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await listTenders(1, 50, status, search);
      setTenders(res.items);
      setTotal(res.total);
      if (res.items.length > 0 && !selectedTender) {
        setSelectedTender(res.items[0]);
      }
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to load tenders from backend.");
    } finally {
      setIsLoading(false);
    }
  }, [selectedTender]);

  useEffect(() => {
    let isMounted = true;
    listTenders(1, 50)
      .then((res) => {
        if (isMounted) {
          setTenders(res.items);
          setTotal(res.total);
          if (res.items.length > 0) {
            setSelectedTender(res.items[0]);
          }
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError((err as Error).message || "Failed to load tenders from backend.");
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadTenders(searchQuery, statusFilter);
  };

  const handleStatusFilter = (status?: string) => {
    setStatusFilter(status);
    loadTenders(searchQuery, status);
  };

  const handleConfirmPublish = async () => {
    if (!publishingTender) return;
    const updated = await publishTender(publishingTender.id);
    setTenders((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    if (selectedTender?.id === updated.id) {
      setSelectedTender(updated);
    }
    setNotification({
      type: "success",
      message: `Tender ${updated.tender_number} has been officially PUBLISHED and is now publicly accessible to prospective bidders!`,
    });
    setTimeout(() => setNotification(null), 6000);
  };

  const handleTenderCreated = (newTender: TenderItem) => {
    setTenders((prev) => [newTender, ...prev]);
    setSelectedTender(newTender);
    setTotal((prev) => prev + 1);
    setNotification({
      type: "info",
      message: `Draft tender ${newTender.tender_number} created successfully.`,
    });
    setTimeout(() => setNotification(null), 5000);
  };

  const draftCount = tenders.filter((t) => t.status === "DRAFT").length;
  const publishedCount = tenders.filter((t) => t.status === "PUBLISHED").length;
  const closedCount = tenders.filter((t) => t.status === "CLOSED").length;

  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="Tender Management & Lifecycle"
          description="Create, configure, publish, and oversee procurement specifications across the official CRPF lifecycle."
          breadcrumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Tenders" }]}
          actions={
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <Link href="/tenders/public" target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>
                <Button variant="outline" size="sm">
                  Public Tender Portal ↗
                </Button>
              </Link>

              {canCreate && (
                <Button variant="primary" size="sm" onClick={() => setIsCreateModalOpen(true)}>
                  + Create Draft Tender
                </Button>
              )}
            </div>
          }
        />

        {notification && (
          <div style={{ marginBottom: "16px" }}>
            <Alert variant={notification.type === "success" ? "success" : "info"} title="Notice">
              {notification.message}
            </Alert>
          </div>
        )}

        {/* Metrics Row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "14px", marginBottom: "20px" }}>
          <div
            style={{
              backgroundColor: "#ffffff",
              padding: "14px 18px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--gov-border)",
            }}
          >
            <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-text-muted)", textTransform: "uppercase" }}>
              Total Tenders
            </div>
            <div style={{ fontSize: "22px", fontWeight: 800, color: "var(--gov-primary)", marginTop: "4px" }}>
              {total}
            </div>
          </div>

          <div
            style={{
              backgroundColor: "#ffffff",
              padding: "14px 18px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--gov-border)",
            }}
          >
            <div style={{ fontSize: "11px", fontWeight: 700, color: "#d97706", textTransform: "uppercase" }}>
              Drafts (Restricted)
            </div>
            <div style={{ fontSize: "22px", fontWeight: 800, color: "#b45309", marginTop: "4px" }}>
              {draftCount}
            </div>
          </div>

          <div
            style={{
              backgroundColor: "#ffffff",
              padding: "14px 18px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--gov-border)",
            }}
          >
            <div style={{ fontSize: "11px", fontWeight: 700, color: "#15803d", textTransform: "uppercase" }}>
              Published / Open
            </div>
            <div style={{ fontSize: "22px", fontWeight: 800, color: "#166534", marginTop: "4px" }}>
              {publishedCount}
            </div>
          </div>

          <div
            style={{
              backgroundColor: "#ffffff",
              padding: "14px 18px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--gov-border)",
            }}
          >
            <div style={{ fontSize: "11px", fontWeight: 700, color: "#475569", textTransform: "uppercase" }}>
              Closed Cycles
            </div>
            <div style={{ fontSize: "22px", fontWeight: 800, color: "#334155", marginTop: "4px" }}>
              {closedCount}
            </div>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <Card style={{ marginBottom: "20px" }}>
          <CardContent style={{ padding: "14px 18px" }}>
            <form onSubmit={handleSearchSubmit} style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" }}>
              <div style={{ flex: 1, minWidth: "240px" }}>
                <Input
                  type="text"
                  placeholder="Search by tender reference or title..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", gap: "6px" }}>
                <Button
                  type="button"
                  variant={statusFilter === undefined ? "primary" : "outline"}
                  size="sm"
                  onClick={() => handleStatusFilter(undefined)}
                >
                  All ({total})
                </Button>
                <Button
                  type="button"
                  variant={statusFilter === "DRAFT" ? "primary" : "outline"}
                  size="sm"
                  onClick={() => handleStatusFilter("DRAFT")}
                >
                  Drafts
                </Button>
                <Button
                  type="button"
                  variant={statusFilter === "PUBLISHED" ? "primary" : "outline"}
                  size="sm"
                  onClick={() => handleStatusFilter("PUBLISHED")}
                >
                  Published
                </Button>
                <Button
                  type="button"
                  variant={statusFilter === "CLOSED" ? "primary" : "outline"}
                  size="sm"
                  onClick={() => handleStatusFilter("CLOSED")}
                >
                  Closed
                </Button>
              </div>

              <Button type="submit" variant="secondary" size="sm">
                🔍 Filter
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Selected Tender Spotlight Box if published or draft */}
        {selectedTender && (
          <div style={{ marginBottom: "20px" }}>
            {selectedTender.status === "PUBLISHED" ? (
              <PublicTenderShareBox tenderId={selectedTender.id} tenderNumber={selectedTender.tender_number} />
            ) : selectedTender.status === "DRAFT" ? (
              <div
                style={{
                  padding: "16px 20px",
                  backgroundColor: "#fffbeb",
                  border: "1px solid #fef3c7",
                  borderRadius: "var(--radius-lg)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span style={{ fontSize: "20px" }}>🔒</span>
                  <div>
                    <div style={{ fontSize: "13px", fontWeight: 700, color: "#92400e" }}>
                      Selected Tender in DRAFT Status: {selectedTender.tender_number}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                      This tender notice is strictly confidential and not accessible to prospective bidders.
                    </div>
                  </div>
                </div>

                {canPublish ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setPublishingTender(selectedTender)}
                    style={{ backgroundColor: "#166534" }}
                  >
                    📢 Publish Tender Now
                  </Button>
                ) : (
                  <span style={{ fontSize: "12px", color: "var(--gov-text-muted)", fontStyle: "italic" }}>
                    Publishing requires TENDER_UPDATE authority
                  </span>
                )}
              </div>
            ) : null}
          </div>
        )}

        {/* Tenders Table */}
        <Card>
          <CardHeader>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <CardTitle style={{ fontSize: "16px" }}>Procurement Tenders Repository</CardTitle>
                <CardDescription>Click any tender row to inspect details or trigger publishing workflow.</CardDescription>
              </div>
              <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                Showing {tenders.length} of {total}
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
                <ErrorState title="Failed to Load Tenders" error={error} onRetry={() => loadTenders(searchQuery, statusFilter)} />
              </div>
            ) : tenders.length === 0 ? (
              <div style={{ padding: "32px 16px" }}>
                <EmptyState
                  icon="📋"
                  title="No Tenders Found"
                  description="No procurement notices match the criteria or repository is empty."
                  action={
                    canCreate ? (
                      <Button variant="primary" size="sm" onClick={() => setIsCreateModalOpen(true)}>
                        Create First Tender
                      </Button>
                    ) : undefined
                  }
                />
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="gov-table" style={{ margin: 0 }}>
                  <thead>
                    <tr>
                      <th>Tender Reference</th>
                      <th>Title & Scope</th>
                      <th>Issuing Wing</th>
                      <th>Version</th>
                      <th>Lifecycle</th>
                      <th>Created</th>
                      <th style={{ textAlign: "right" }}>Lifecycle Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tenders.map((t) => {
                      const isSelected = selectedTender?.id === t.id;
                      return (
                        <tr
                          key={t.id}
                          onClick={() => setSelectedTender(t)}
                          style={{
                            backgroundColor: isSelected ? "rgba(11, 37, 69, 0.04)" : undefined,
                            cursor: "pointer",
                          }}
                        >
                          <td style={{ fontWeight: 700, color: "var(--gov-primary)", whiteSpace: "nowrap" }}>
                            {t.tender_number}
                          </td>
                          <td style={{ maxWidth: "260px" }}>
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
                            {t.status === "DRAFT" ? (
                              canPublish ? (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setPublishingTender(t);
                                  }}
                                  style={{ borderColor: "#166534", color: "#166534" }}
                                >
                                  Publish Tender
                                </Button>
                              ) : (
                                <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>Draft</span>
                              )
                            ) : t.status === "PUBLISHED" ? (
                              <div style={{ display: "inline-flex", gap: "6px" }} onClick={(e) => e.stopPropagation()}>
                                <Link
                                  href={`/tenders/public/${t.id}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{ textDecoration: "none" }}
                                >
                                  <Button variant="ghost" size="sm">
                                    Public View ↗
                                  </Button>
                                </Link>
                              </div>
                            ) : (
                              <span style={{ fontSize: "12px", color: "var(--gov-text-muted)" }}>Archived</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Publish Confirmation Modal */}
        {publishingTender && (
          <PublishTenderModal
            tender={publishingTender}
            isOpen={Boolean(publishingTender)}
            onClose={() => setPublishingTender(null)}
            onConfirmPublish={handleConfirmPublish}
          />
        )}

        {/* Create Draft Tender Modal */}
        <CreateTenderModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onTenderCreated={handleTenderCreated}
        />
      </PageContainer>
    </AppShell>
  );
}

export default function TendersPage() {
  return (
    <ProtectedRoute requiredPermission="TENDER_READ">
      <OfficerTendersContent />
    </ProtectedRoute>
  );
}
