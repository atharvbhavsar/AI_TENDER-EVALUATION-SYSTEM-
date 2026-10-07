"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { listPublicTenders, type TenderItem } from "@/lib/api/tenders";

export default function PublicTendersPage() {
  const [tenders, setTenders] = useState<TenderItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"PUBLISHED" | "CLOSED" | undefined>(undefined);

  const fetchPublicData = useCallback(async (search?: string, status?: "PUBLISHED" | "CLOSED") => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await listPublicTenders(1, 20, search, status);
      setTenders(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      setError((err as Error).message || "Unable to retrieve published tenders from the central repository.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    listPublicTenders(1, 20)
      .then((res) => {
        if (isMounted) {
          setTenders(res.items);
          setTotal(res.total);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError((err as Error).message || "Unable to retrieve published tenders from the central repository.");
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchPublicData(searchQuery, statusFilter);
  };

  const handleFilterChange = (newStatus: "PUBLISHED" | "CLOSED" | undefined) => {
    setStatusFilter(newStatus);
    fetchPublicData(searchQuery, newStatus);
  };

  return (
    <AppShell showSidebar={false}>
      {/* Public Banner */}
      <div
        style={{
          backgroundColor: "#0b2545",
          color: "#ffffff",
          padding: "24px 20px",
          borderBottom: "3px solid var(--gov-gold)",
        }}
      >
        <div style={{ maxWidth: "1280px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "8px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                backgroundColor: "rgba(255, 255, 255, 0.15)",
                padding: "2px 8px",
                borderRadius: "4px",
                color: "#fef9c3",
              }}
            >
              Public Procurement Portal
            </span>
            <span style={{ fontSize: "12px", opacity: 0.8 }}>Central Reserve Police Force</span>
          </div>

          <h1 style={{ margin: 0, fontSize: "24px", fontWeight: 800, letterSpacing: "-0.02em" }}>
            Public Tender Notices & Procurement Opportunities
          </h1>
          <p style={{ margin: 0, fontSize: "13px", color: "#93c5fd", maxWidth: "800px", lineHeight: 1.4 }}>
            Explore official procurement notices, download technical specifications, and examine eligibility criteria for CRPF equipment, supplies, and services.
          </p>
        </div>
      </div>

      <PageContainer maxWidth="xl">
        <PageHeader
          title="Open & Published Tenders"
          description={`Displaying ${total} procurement opportunities currently published for public bidding.`}
          breadcrumbs={[{ label: "Public Portal" }]}
          actions={
            <Link href="/login" style={{ textDecoration: "none" }}>
              <Button variant="outline" size="sm">
                Officer Login 🔒
              </Button>
            </Link>
          }
        />

        {/* Search and Filters Bar */}
        <Card style={{ marginBottom: "24px" }}>
          <CardContent style={{ padding: "16px 20px" }}>
            <form onSubmit={handleSearchSubmit} style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center" }}>
              <div style={{ flex: 1, minWidth: "260px" }}>
                <Input
                  type="text"
                  placeholder="Search by tender reference (e.g. CRPF/PROC/2026) or keyword..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", gap: "6px" }}>
                <Button
                  type="button"
                  variant={statusFilter === undefined ? "primary" : "outline"}
                  size="sm"
                  onClick={() => handleFilterChange(undefined)}
                >
                  All Statuses
                </Button>
                <Button
                  type="button"
                  variant={statusFilter === "PUBLISHED" ? "primary" : "outline"}
                  size="sm"
                  onClick={() => handleFilterChange("PUBLISHED")}
                >
                  Open for Bids
                </Button>
                <Button
                  type="button"
                  variant={statusFilter === "CLOSED" ? "primary" : "outline"}
                  size="sm"
                  onClick={() => handleFilterChange("CLOSED")}
                >
                  Closed
                </Button>
              </div>

              <Button type="submit" variant="secondary" size="sm">
                🔍 Search
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Results Area */}
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <Skeleton width="100%" height="110px" />
            <Skeleton width="100%" height="110px" />
            <Skeleton width="100%" height="110px" />
          </div>
        ) : error ? (
          <ErrorState
            title="Failed to Load Public Tenders"
            error={error}
            onRetry={() => fetchPublicData(searchQuery, statusFilter)}
          />
        ) : tenders.length === 0 ? (
          <EmptyState
            icon="📄"
            title="No Published Tenders Found"
            description="There are currently no procurement tenders matching your search criteria. Check back soon or clear search filters."
            action={
              (searchQuery || statusFilter) && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearchQuery("");
                    setStatusFilter(undefined);
                    fetchPublicData("", undefined);
                  }}
                >
                  Clear Search Filters
                </Button>
              )
            }
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {tenders.map((tender) => (
              <Card key={tender.id} className="hover:shadow-md transition-shadow">
                <CardHeader style={{ paddingBottom: "10px" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: "10px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                        <span
                          style={{
                            fontFamily: "var(--font-family-mono)",
                            fontSize: "13px",
                            fontWeight: 700,
                            color: "var(--gov-primary)",
                          }}
                        >
                          {tender.tender_number}
                        </span>
                        <StatusBadge status={tender.status} size="sm" />
                      </div>
                      <CardTitle style={{ fontSize: "16px" }}>{tender.title}</CardTitle>
                    </div>

                    <div style={{ textAlign: "right" }}>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          backgroundColor: "var(--gov-surface-secondary)",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          color: "var(--gov-text-secondary)",
                        }}
                      >
                        {tender.active_version ? `v${tender.active_version.version_number} (${tender.active_version.version_label})` : "v1"}
                      </span>
                    </div>
                  </div>

                  {tender.description && (
                    <CardDescription style={{ marginTop: "6px", fontSize: "13px", lineHeight: 1.4 }}>
                      {tender.description}
                    </CardDescription>
                  )}
                </CardHeader>

                <CardContent style={{ paddingTop: 0 }}>
                  <div
                    style={{
                      borderTop: "1px solid var(--gov-border)",
                      paddingTop: "12px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "12px",
                      fontSize: "12px",
                      color: "var(--gov-text-muted)",
                    }}
                  >
                    <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                      <span>
                        Authority: <strong style={{ color: "var(--gov-text-secondary)" }}>{tender.issuing_authority}</strong>
                      </span>
                      <span>
                        Published: <strong style={{ color: "var(--gov-text-secondary)" }}>{new Date(tender.created_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</strong>
                      </span>
                    </div>

                    <Link href={`/tenders/public/${tender.id}`} style={{ textDecoration: "none" }}>
                      <Button variant="primary" size="sm">
                        View Tender Requirements & Specs →
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </PageContainer>
    </AppShell>
  );
}
