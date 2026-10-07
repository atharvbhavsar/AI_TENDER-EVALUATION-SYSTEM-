"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AppShell, PageContainer } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { Alert } from "@/components/ui/Alert";
import { useAuth } from "@/context/AuthContext";
import {
  getPublicTender,
  listPublicTenderDocuments,
  getPublicDocumentDownloadUrl,
  type TenderItem,
  type PublicDocumentItem,
} from "@/lib/api/tenders";
import { applyForTender } from "@/lib/api/bidder";

export default function PublicTenderDetailPage() {
  const params = useParams<{ tenderId: string }>();
  const router = useRouter();
  const { isAuthenticated, hasRole } = useAuth();
  const tenderId = params?.tenderId;

  const [tender, setTender] = useState<TenderItem | null>(null);
  const [documents, setDocuments] = useState<PublicDocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [is404Draft, setIs404Draft] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  const loadPublicTender = useCallback(async () => {
    if (!tenderId) return;
    setIsLoading(true);
    setError(null);
    setIs404Draft(false);

    try {
      const tenderData = await getPublicTender(tenderId);
      setTender(tenderData);

      // Fetch public documents
      try {
        const docRes = await listPublicTenderDocuments(tenderId);
        setDocuments(docRes.items);
      } catch {
        // Non-fatal if documents list is empty
      }
    } catch (err: unknown) {
      const status = (err as { info?: { statusCode?: number } })?.info?.statusCode;
      if (status === 404) {
        setIs404Draft(true);
      } else {
        setError((err as Error).message || "Unable to load public tender specifications.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [tenderId]);

  useEffect(() => {
    if (!tenderId) return;
    let isMounted = true;

    getPublicTender(tenderId)
      .then(async (tenderData) => {
        if (!isMounted) return;
        setTender(tenderData);
        try {
          const docRes = await listPublicTenderDocuments(tenderId);
          if (isMounted) setDocuments(docRes.items);
        } catch {
          // ignore
        }
        if (isMounted) setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        const status = (err as { info?: { statusCode?: number } })?.info?.statusCode;
        if (status === 404) {
          setIs404Draft(true);
        } else {
          setError((err as Error).message || "Unable to load public tender specifications.");
        }
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [tenderId]);

  const handleApply = async () => {
    if (!tenderId) return;

    if (!isAuthenticated) {
      router.push(`/login?returnUrl=${encodeURIComponent(`/tenders/public/${tenderId}`)}`);
      return;
    }

    if (!hasRole("BIDDER")) {
      setApplyError("You are logged in with an officer/staff account. Bidding requires a registered corporate Bidder account.");
      return;
    }

    setIsApplying(true);
    setApplyError(null);
    try {
      const application = await applyForTender(tenderId);
      router.push(`/bidder/applications/${application.id}`);
    } catch (err: unknown) {
      setApplyError((err as Error).message || "Failed to initiate application for this tender.");
    } finally {
      setIsApplying(false);
    }
  };

  const isClosed = tender?.status === "CLOSED";

  return (
    <AppShell showSidebar={false}>
      {/* Public Government Banner */}
      <div
        style={{
          backgroundColor: "#0b2545",
          color: "#ffffff",
          padding: "20px 24px",
          borderBottom: "3px solid var(--gov-gold)",
        }}
      >
        <div style={{ maxWidth: "1280px", margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: "11px", color: "#93c5fd", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700 }}>
              Central Reserve Police Force • Public Procurement Portal
            </div>
            <div style={{ fontSize: "16px", fontWeight: 700, marginTop: "2px" }}>
              Official Notice Inviting Tender (NIT)
            </div>
          </div>

          <Link href="/tenders/public" style={{ textDecoration: "none" }}>
            <Button variant="outline" size="sm" style={{ borderColor: "rgba(255,255,255,0.4)", color: "#ffffff" }}>
              ← All Public Tenders
            </Button>
          </Link>
        </div>
      </div>

      <PageContainer maxWidth="xl">
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px", marginTop: "24px" }}>
            <Skeleton width="60%" height="40px" />
            <Skeleton width="100%" height="200px" />
            <Skeleton width="100%" height="300px" />
          </div>
        ) : is404Draft ? (
          <div style={{ marginTop: "48px" }}>
            <Card style={{ maxWidth: "600px", margin: "0 auto", textAlign: "center", padding: "32px 24px" }}>
              <div style={{ fontSize: "40px", marginBottom: "12px" }}>🔒</div>
              <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--gov-text-primary)", margin: "0 0 8px 0" }}>
                Tender Notice Not Publicly Available
              </h2>
              <p style={{ fontSize: "13px", color: "var(--gov-text-muted)", margin: "0 0 20px 0", lineHeight: 1.5 }}>
                The requested tender is currently in draft preparation stage or has been archived. Draft procurement specifications are restricted to authorized procurement officers.
              </p>
              <div style={{ display: "flex", justifyContent: "center", gap: "12px" }}>
                <Link href="/tenders/public" style={{ textDecoration: "none" }}>
                  <Button variant="primary" size="md">
                    Browse Active Tenders
                  </Button>
                </Link>
                <Link href="/login" style={{ textDecoration: "none" }}>
                  <Button variant="outline" size="md">
                    Officer Sign In
                  </Button>
                </Link>
              </div>
            </Card>
          </div>
        ) : error || !tender ? (
          <div style={{ marginTop: "24px" }}>
            <ErrorState title="Error Loading Tender Notice" error={error} onRetry={loadPublicTender} />
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px", marginTop: "16px" }}>
            {/* Top Tender Identification Card */}
            <Card>
              <CardHeader>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                      <span
                        style={{
                          fontFamily: "var(--font-family-mono)",
                          fontSize: "14px",
                          fontWeight: 700,
                          color: "var(--gov-primary)",
                          backgroundColor: "var(--gov-surface-secondary)",
                          padding: "3px 8px",
                          borderRadius: "4px",
                        }}
                      >
                        {tender.tender_number}
                      </span>
                      <StatusBadge status={tender.status} size="md" />
                      {tender.active_version && (
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 700,
                            padding: "2px 8px",
                            borderRadius: "4px",
                            backgroundColor: "var(--gov-surface-secondary)",
                            color: "var(--gov-text-secondary)",
                          }}
                        >
                          v{tender.active_version.version_number} ({tender.active_version.version_label})
                        </span>
                      )}
                    </div>

                    <CardTitle style={{ fontSize: "22px" }}>{tender.title}</CardTitle>
                    <CardDescription style={{ fontSize: "13px", marginTop: "4px" }}>
                      Issuing Authority: <strong>{tender.issuing_authority}</strong>
                    </CardDescription>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "8px" }}>
                    <div
                      style={{
                        textAlign: "right",
                        fontSize: "12px",
                        color: "var(--gov-text-muted)",
                      }}
                    >
                      Published:{" "}
                      <strong style={{ color: "var(--gov-text-secondary)" }}>
                        {new Date(tender.created_at).toLocaleDateString("en-IN", {
                          day: "2-digit",
                          month: "long",
                          year: "numeric",
                        })}
                      </strong>
                    </div>

                    {!isClosed ? (
                      <Button
                        variant="primary"
                        size="md"
                        isLoading={isApplying}
                        onClick={handleApply}
                        style={{ backgroundColor: "#166534" }}
                      >
                        Apply for Tender →
                      </Button>
                    ) : (
                      <span
                        style={{
                          padding: "6px 14px",
                          borderRadius: "var(--radius-md)",
                          backgroundColor: "#fef2f2",
                          color: "#991b1b",
                          fontSize: "12px",
                          fontWeight: 700,
                          border: "1px solid #fca5a5",
                        }}
                      >
                        Submissions Closed
                      </span>
                    )}
                  </div>
                </div>

                {applyError && (
                  <div style={{ marginTop: "12px" }}>
                    <Alert variant="warning" title="Application Notice">
                      {applyError}
                    </Alert>
                  </div>
                )}
              </CardHeader>

              {tender.description && (
                <CardContent style={{ borderTop: "1px solid var(--gov-border)", paddingTop: "16px" }}>
                  <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--gov-text-secondary)", textTransform: "uppercase", marginBottom: "6px" }}>
                    Scope of Procurement & Overview
                  </div>
                  <div style={{ fontSize: "14px", color: "var(--gov-text-primary)", lineHeight: 1.6 }}>
                    {tender.description}
                  </div>
                </CardContent>
              )}
            </Card>

            {/* Submission Deadline & Public Status Banner */}
            <div
              style={{
                padding: "16px 20px",
                borderRadius: "var(--radius-lg)",
                backgroundColor: isClosed ? "#fef2f2" : "#f0fdf4",
                border: `1px solid ${isClosed ? "#fca5a5" : "#86efac"}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "20px" }}>{isClosed ? "⌛" : "⏰"}</span>
                <div>
                  <div style={{ fontSize: "13px", fontWeight: 700, color: isClosed ? "#991b1b" : "#166534" }}>
                    {isClosed ? "Submission Window Concluded" : "Open for Bid Submission"}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--gov-text-muted)" }}>
                    {isClosed
                      ? "Submissions are no longer accepted for this procurement cycle."
                      : "Prospective vendors holding valid DSC certificates can prepare technical proposals."}
                  </div>
                </div>
              </div>

              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--gov-text-muted)", fontWeight: 600 }}>
                  Submission Cutoff
                </div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--gov-text-primary)" }}>
                  30 September 2026, 17:00 IST
                </div>
              </div>
            </div>

            {/* Two-Column Grid: Eligibility Requirements & Mandatory Document Checklist */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "20px" }}>
              {/* Mandatory Eligibility Criteria */}
              <Card>
                <CardHeader>
                  <CardTitle style={{ fontSize: "16px" }}>Mandatory Eligibility Criteria</CardTitle>
                  <CardDescription>Minimum regulatory qualifications for prospective bidders.</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", lineHeight: 1.8, color: "var(--gov-text-secondary)" }}>
                    <li>
                      <strong>Financial Turnover:</strong> Average annual financial turnover of at least ₹50 Crore over the last three audited fiscal years.
                    </li>
                    <li>
                      <strong>Past Experience:</strong> Successful supply of comparable equipment/services to Central Armed Police Forces or Defence agencies.
                    </li>
                    <li>
                      <strong>Quality Standards:</strong> Certification under ISO 9001:2015 and relevant Indian Bureau of Standards (BIS) test certificates.
                    </li>
                    <li>
                      <strong>Statutory Integrity:</strong> No active debarment or blacklisting by CRPF, MHA, or any Government of India department.
                    </li>
                    <li>
                      <strong>Class I Local Supplier:</strong> Local value addition compliance pursuant to Public Procurement (Preference to Make in India) Order.
                    </li>
                  </ul>
                </CardContent>
              </Card>

              {/* Mandatory Document Checklist */}
              <Card>
                <CardHeader>
                  <CardTitle style={{ fontSize: "16px" }}>Required Documents Checklist</CardTitle>
                  <CardDescription>Mandatory verification records to be submitted by the bidder.</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", lineHeight: 1.8, color: "var(--gov-text-secondary)" }}>
                    <li>Certificate of Incorporation / Registration of Partnership Firm.</li>
                    <li>Valid GSTIN Registration Certificate & Latest Filed GSTR-3B.</li>
                    <li>Permanent Account Number (PAN) allotted by Income Tax Department.</li>
                    <li>Statutory Auditor certified Balance Sheets for FY 2023-24, 2024-25, 2025-26.</li>
                    <li>Original Equipment Manufacturer (OEM) Authorization in prescribed format.</li>
                    <li>Clause-by-Clause Technical Compliance Statement signed and stamped.</li>
                  </ul>
                </CardContent>
              </Card>
            </div>

            {/* Public Downloadable Tender Documents */}
            <Card>
              <CardHeader>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <CardTitle style={{ fontSize: "16px" }}>Official Tender Documents & Downloads</CardTitle>
                    <CardDescription>
                      Download authoritative specifications, Notice Inviting Tender (NIT), and schedule of requirements.
                    </CardDescription>
                  </div>
                  <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-text-muted)" }}>
                    {documents.length} Available
                  </span>
                </div>
              </CardHeader>

              <CardContent>
                {documents.length === 0 ? (
                  <div
                    style={{
                      padding: "20px",
                      textAlign: "center",
                      backgroundColor: "var(--gov-surface-secondary)",
                      borderRadius: "var(--radius-md)",
                      fontSize: "12px",
                      color: "var(--gov-text-muted)",
                    }}
                  >
                    Standard Notice Inviting Tender (NIT) specifications package attached with this tender notice.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {documents.map((doc) => (
                      <div
                        key={doc.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 14px",
                          borderRadius: "var(--radius-md)",
                          backgroundColor: "var(--gov-surface-secondary)",
                          fontSize: "12px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span style={{ fontSize: "16px" }}>📄</span>
                          <div>
                            <div style={{ fontWeight: 600, color: "var(--gov-text-primary)" }}>{doc.filename}</div>
                            <div style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                              {doc.document_type} • {(doc.file_size / 1024).toFixed(1)} KB
                            </div>
                          </div>
                        </div>

                        <a
                          href={getPublicDocumentDownloadUrl(tender.id, doc.id)}
                          download={doc.filename}
                          style={{ textDecoration: "none" }}
                        >
                          <Button variant="outline" size="sm">
                            Download Securely ⬇
                          </Button>
                        </a>
                      </div>
                    ))}
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
