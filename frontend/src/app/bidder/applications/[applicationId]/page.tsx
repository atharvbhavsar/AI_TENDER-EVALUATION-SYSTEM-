"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import { Alert } from "@/components/ui/Alert";
import { ErrorState } from "@/components/ui/ErrorState";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import {
  getBidderApplication,
  updateApplicationDraft,
  submitApplication,
  uploadApplicationDocument,
  deleteApplicationDocument,
  downloadApplicationDocument,
  type ApplicationDetailResponse,
  type BidderDocument,
  type CriterionChecklistItem,
} from "@/lib/api/bidder";

const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".xlsx", ".jpg", ".jpeg", ".png"];
const MAX_FILE_SIZE_MB = 50;

function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

function ApplicationDetailContent() {
  const params = useParams<{ applicationId: string }>();
  const applicationId = params?.applicationId;

  const [application, setApplication] = useState<ApplicationDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  // Form editing states
  const [commercialQuote, setCommercialQuote] = useState<string>("");
  const [bidderNotes, setBidderNotes] = useState<string>("");
  const [declarationSigned, setDeclarationSigned] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);

  // Document states
  const [uploadingCriterionId, setUploadingCriterionId] = useState<string | null>(null);
  const [isUploadingGeneral, setIsUploadingGeneral] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<BidderDocument | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [downloadingDocId, setDownloadingDocId] = useState<string | null>(null);

  const generalFileInputRef = useRef<HTMLInputElement | null>(null);

  const reloadApplicationData = useCallback(async () => {
    if (!applicationId) return;
    try {
      const data = await getBidderApplication(applicationId);
      setApplication(data);
      setCommercialQuote(
        data.commercial_quote !== null && data.commercial_quote !== undefined
          ? String(data.commercial_quote)
          : ""
      );
      setBidderNotes(data.bidder_notes || "");
      setDeclarationSigned(Boolean(data.declaration_signed));
    } catch (err: unknown) {
      const status = (err as { info?: { statusCode?: number } })?.info?.statusCode;
      if (status === 404 || status === 403) {
        setIsNotFound(true);
      } else {
        setError((err as Error).message || "Failed to reload application details.");
      }
    }
  }, [applicationId]);

  const handleRetry = useCallback(() => {
    if (!applicationId) return;
    setIsLoading(true);
    setError(null);
    reloadApplicationData().finally(() => setIsLoading(false));
  }, [applicationId, reloadApplicationData]);

  useEffect(() => {
    if (!applicationId) return;
    let isMounted = true;

    getBidderApplication(applicationId)
      .then((data) => {
        if (isMounted) {
          setApplication(data);
          setCommercialQuote(
            data.commercial_quote !== null && data.commercial_quote !== undefined
              ? String(data.commercial_quote)
              : ""
          );
          setBidderNotes(data.bidder_notes || "");
          setDeclarationSigned(Boolean(data.declaration_signed));
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        const status = (err as { info?: { statusCode?: number } })?.info?.statusCode;
        if (status === 404 || status === 403) {
          setIsNotFound(true);
        } else {
          setError((err as Error).message || "Failed to load application details.");
        }
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [applicationId]);

  // Handle ESC key for modal dismissals
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (showSubmitModal) setShowSubmitModal(false);
        if (documentToDelete) setDocumentToDelete(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showSubmitModal, documentToDelete]);

  const handleSaveDraft = async () => {
    if (!applicationId || !application) return;
    setIsSaving(true);
    setActionError(null);
    setSuccessMessage(null);

    const parsedQuote = commercialQuote.trim() === "" ? undefined : parseFloat(commercialQuote);
    if (parsedQuote !== undefined && (isNaN(parsedQuote) || parsedQuote < 0)) {
      setActionError("Commercial quote must be a valid positive number in INR.");
      setIsSaving(false);
      return;
    }

    try {
      const updated = await updateApplicationDraft(applicationId, {
        commercial_quote: parsedQuote,
        bidder_notes: bidderNotes.trim() === "" ? undefined : bidderNotes,
        declaration_signed: declarationSigned,
      });
      setApplication(updated);
      setSuccessMessage("Draft proposal successfully saved.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      setActionError((err as Error).message || "Failed to save draft changes.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleConfirmSubmit = async () => {
    if (!applicationId || !application) return;
    setIsSubmitting(true);
    setActionError(null);

    const parsedQuote = commercialQuote.trim() === "" ? undefined : parseFloat(commercialQuote);
    if (parsedQuote !== undefined && (isNaN(parsedQuote) || parsedQuote < 0)) {
      setActionError("Commercial quote must be a valid positive number in INR.");
      setIsSubmitting(false);
      setShowSubmitModal(false);
      return;
    }

    try {
      const submitted = await submitApplication(applicationId, {
        confirm_declaration: true,
        commercial_quote: parsedQuote,
        bidder_notes: bidderNotes.trim() === "" ? undefined : bidderNotes,
      });
      setApplication(submitted);
      setShowSubmitModal(false);
      setSuccessMessage("Application successfully submitted and locked. Official submission receipt generated.");
    } catch (err: unknown) {
      setActionError((err as Error).message || "Submission failed. Please review error.");
      setShowSubmitModal(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const validateFileBeforeUpload = (file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file format '${ext}'. Permitted types: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      return `File size exceeds the maximum limit of ${MAX_FILE_SIZE_MB} MB (${formatBytes(file.size)}).`;
    }
    if (file.size === 0) {
      return "Selected file is empty (0 bytes).";
    }
    return null;
  };

  const handleFileUpload = async (file: File, criterionId?: string) => {
    if (!applicationId || !application) return;
    setActionError(null);
    setSuccessMessage(null);

    const validationErr = validateFileBeforeUpload(file);
    if (validationErr) {
      setActionError(validationErr);
      return;
    }

    if (criterionId) {
      setUploadingCriterionId(criterionId);
    } else {
      setIsUploadingGeneral(true);
    }

    try {
      await uploadApplicationDocument(applicationId, file, criterionId);
      setSuccessMessage(`Document "${file.name}" successfully uploaded and verified.`);
      await reloadApplicationData();
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      setActionError((err as Error).message || "Failed to upload document.");
    } finally {
      setUploadingCriterionId(null);
      setIsUploadingGeneral(false);
    }
  };

  const handleDownload = async (doc: BidderDocument) => {
    if (!applicationId) return;
    setDownloadingDocId(doc.id);
    setActionError(null);
    try {
      await downloadApplicationDocument(applicationId, doc.id, doc.filename);
    } catch (err: unknown) {
      setActionError((err as Error).message || `Failed to download ${doc.filename}.`);
    } finally {
      setDownloadingDocId(null);
    }
  };

  const handleConfirmDeleteDocument = async () => {
    if (!applicationId || !documentToDelete) return;
    setIsDeleting(true);
    setActionError(null);
    try {
      const resp = await deleteApplicationDocument(applicationId, documentToDelete.id);
      setSuccessMessage(resp.message || `Document "${documentToDelete.filename}" removed.`);
      setDocumentToDelete(null);
      await reloadApplicationData();
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      setActionError((err as Error).message || "Failed to remove document.");
      setDocumentToDelete(null);
    } finally {
      setIsDeleting(false);
    }
  };

  if (isNotFound) {
    return (
      <AppShell>
        <PageContainer maxWidth="lg">
          <div style={{ marginTop: "40px" }}>
            <Card style={{ textAlign: "center", padding: "36px 20px" }}>
              <div style={{ fontSize: "40px", marginBottom: "12px" }}>🔒</div>
              <h2 style={{ fontSize: "18px", fontWeight: 700, margin: "0 0 8px 0" }}>
                Application Record Not Accessible
              </h2>
              <p style={{ fontSize: "13px", color: "var(--gov-text-muted)", maxWidth: "480px", margin: "0 auto 24px auto" }}>
                This application identifier does not exist or belongs to another registered vendor entity. Pursuant to procurement data isolation policies, cross-bidder records cannot be inspected.
              </p>
              <Link href="/bidder/applications" style={{ textDecoration: "none" }}>
                <Button variant="primary" size="md">
                  Return to My Applications
                </Button>
              </Link>
            </Card>
          </div>
        </PageContainer>
      </AppShell>
    );
  }

  const isSubmitted = application?.status === "SUBMITTED" || application?.is_locked;
  const isEditable = Boolean(application?.can_edit && !isSubmitted);

  // Compute deadline formatted string
  let deadlineString = "Not specified";
  let isExpired = false;
  if (application?.submission_deadline) {
    const deadlineDate = new Date(application.submission_deadline);
    deadlineString =
      deadlineDate.toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      }) + " IST";
    isExpired = Boolean(application.is_deadline_passed);
  }

  // Calculate completeness progress
  const mandatoryCriteria = application?.criteria_checklist.filter((c) => c.mandatory) || [];
  const uploadedDocs = application?.documents || [];
  const mandatoryUploadedCount = mandatoryCriteria.filter((c) =>
    uploadedDocs.some((d) => d.criterion_id === c.id)
  ).length;
  const mandatoryTotalCount = mandatoryCriteria.length;
  const completenessPercent =
    mandatoryTotalCount > 0 ? Math.round((mandatoryUploadedCount / mandatoryTotalCount) * 100) : 100;

  // Split documents by criterion vs general
  const generalDocuments = uploadedDocs.filter((d) => !d.criterion_id);

  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px", marginTop: "20px" }}>
            <Skeleton width="40%" height="32px" />
            <Skeleton width="100%" height="160px" />
            <Skeleton width="100%" height="300px" />
          </div>
        ) : error || !application ? (
          <div style={{ marginTop: "20px" }}>
            <ErrorState
              title="Error Loading Application"
              error={error || "Application not found"}
              onRetry={handleRetry}
            />
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            <PageHeader
              title={`Application: ${application.submission_reference}`}
              description={`Registered response against tender ${application.tender_number}`}
              breadcrumbs={[
                { label: "Bidder Portal", href: "/bidder/dashboard" },
                { label: "My Applications", href: "/bidder/applications" },
                { label: application.submission_reference },
              ]}
              badge={<StatusBadge status={application.status} size="md" />}
              actions={
                <Link
                  href={`/tenders/public/${application.tender_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: "none" }}
                >
                  <Button variant="outline" size="sm">
                    View Public Tender Notice ↗
                  </Button>
                </Link>
              }
            />

            {/* Notification & Feedback Banners */}
            {actionError && (
              <Alert variant="danger" title="Action Error">
                {actionError}
              </Alert>
            )}

            {successMessage && (
              <Alert variant="success" title="Success">
                {successMessage}
              </Alert>
            )}

            {/* Post-Submission Receipt Banner */}
            {isSubmitted && (
              <div
                style={{
                  backgroundColor: "#ecfdf5",
                  border: "2px solid #059669",
                  borderRadius: "8px",
                  padding: "20px 24px",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.05)",
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: "16px" }}>
                  <div style={{ fontSize: "32px", lineHeight: 1 }}>🛡️</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                      <h3 style={{ fontSize: "18px", fontWeight: 700, color: "#065f46", margin: 0 }}>
                        Official Submission Receipt & Sealed Bid
                      </h3>
                      <span
                        style={{
                          backgroundColor: "#059669",
                          color: "#ffffff",
                          fontSize: "11px",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: "4px",
                          letterSpacing: "0.5px",
                        }}
                      >
                        SEALED & LOCKED
                      </span>
                    </div>
                    <p style={{ fontSize: "13px", color: "#047857", margin: "6px 0 14px 0" }}>
                      Your bid application and uploaded evidentiary documents are permanently locked in the central repository. Modifications are strictly disabled.
                    </p>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                        gap: "12px",
                        backgroundColor: "#ffffff",
                        padding: "12px 16px",
                        borderRadius: "6px",
                        border: "1px solid #a7f3d0",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "11px", color: "#065f46", fontWeight: 600, textTransform: "uppercase" }}>
                          Receipt Reference
                        </div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#111827", marginTop: "2px" }}>
                          {application.submission_reference}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: "11px", color: "#065f46", fontWeight: 600, textTransform: "uppercase" }}>
                          Submission Timestamp
                        </div>
                        <div style={{ fontSize: "13px", fontWeight: 600, color: "#111827", marginTop: "2px" }}>
                          {application.submitted_at
                            ? new Date(application.submitted_at).toLocaleString("en-IN", {
                                timeZone: "Asia/Kolkata",
                                day: "2-digit",
                                month: "long",
                                year: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                                second: "2-digit",
                                hour12: true,
                              }) + " IST"
                            : "Recorded"}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: "11px", color: "#065f46", fontWeight: 600, textTransform: "uppercase" }}>
                          Sealed Documents
                        </div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "#111827", marginTop: "2px" }}>
                          {uploadedDocs.length} Document(s) Ingested
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Deadline Expired Warning */}
            {!isSubmitted && isExpired && (
              <Alert variant="danger" title="Submission Deadline Passed">
                The official cutoff deadline for this tender was <strong>{deadlineString}</strong>. Submissions and document uploads are closed.
              </Alert>
            )}

            {/* Tender Overview Card */}
            <Card>
              <CardHeader>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
                  <div>
                    <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-text-muted)", textTransform: "uppercase" }}>
                      Target Tender Opportunity
                    </div>
                    <CardTitle style={{ fontSize: "18px", marginTop: "2px" }}>
                      {application.tender_title}
                    </CardTitle>
                    <CardDescription style={{ marginTop: "4px" }}>
                      Authority: <strong>{application.issuing_authority}</strong> • Specification:{" "}
                      <strong>v{application.version_number} ({application.version_label})</strong>
                    </CardDescription>
                  </div>

                  <div style={{ textAlign: "right", fontSize: "12px", color: "var(--gov-text-muted)" }}>
                    <div>Registered: <strong>{new Date(application.created_at).toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" })}</strong></div>
                    <div style={{ marginTop: "4px" }}>
                      Cutoff Deadline: <strong style={{ color: isExpired ? "#dc2626" : "inherit" }}>{deadlineString}</strong>
                    </div>
                  </div>
                </div>
              </CardHeader>
            </Card>

            {/* Document Completeness Progress Banner */}
            <Card>
              <CardContent style={{ padding: "20px 24px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <div>
                    <h3 style={{ fontSize: "15px", fontWeight: 700, color: "var(--gov-text-primary)", margin: 0 }}>
                      Mandatory Document Completeness
                    </h3>
                    <p style={{ fontSize: "12px", color: "var(--gov-text-muted)", margin: "2px 0 0 0" }}>
                      {mandatoryTotalCount > 0
                        ? `${mandatoryUploadedCount} of ${mandatoryTotalCount} mandatory requirements satisfied (${completenessPercent}%)`
                        : "No mandatory document requirements established for this tender version."}
                    </p>
                  </div>
                  <span
                    style={{
                      fontSize: "14px",
                      fontWeight: 700,
                      color: completenessPercent === 100 ? "#059669" : "var(--gov-primary)",
                    }}
                  >
                    {completenessPercent}%
                  </span>
                </div>

                <div
                  style={{
                    height: "8px",
                    width: "100%",
                    backgroundColor: "var(--gov-surface-secondary)",
                    borderRadius: "4px",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${completenessPercent}%`,
                      backgroundColor: completenessPercent === 100 ? "#059669" : "var(--gov-primary)",
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
              </CardContent>
            </Card>

            {/* Required Documents Checklist & Upload Cards */}
            <Card>
              <CardHeader>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <CardTitle style={{ fontSize: "16px" }}>
                      Required Documents & Specification Proofs
                    </CardTitle>
                    <CardDescription>
                      Upload authoritative evidence (PDF, Word DOCX, Image, Excel $\le 50$MB) for each tender requirement.
                    </CardDescription>
                  </div>
                  <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-text-muted)" }}>
                    {application.criteria_checklist.length} Requirement(s)
                  </span>
                </div>
              </CardHeader>

              <CardContent style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {application.criteria_checklist.length === 0 ? (
                  <div style={{ padding: "16px", textAlign: "center", color: "var(--gov-text-muted)", fontSize: "13px" }}>
                    No specific checklist criteria found for this tender version. You may upload general supporting documents below.
                  </div>
                ) : (
                  application.criteria_checklist.map((criterion: CriterionChecklistItem) => {
                    const matchedDoc = uploadedDocs.find((d) => d.criterion_id === criterion.id);
                    const isUploadingThis = uploadingCriterionId === criterion.id;

                    return (
                      <div
                        key={criterion.id}
                        id={`criterion-card-${criterion.criterion_code}`}
                        style={{
                          border: matchedDoc ? "1px solid #10b981" : "1px solid var(--gov-border)",
                          borderRadius: "8px",
                          backgroundColor: matchedDoc ? "#f0fdf4" : "var(--gov-surface-secondary)",
                          padding: "18px 20px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "12px",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px" }}>
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--gov-primary)" }}>
                                {criterion.criterion_code}
                              </span>
                              <span style={{ fontSize: "14px", fontWeight: 600, color: "var(--gov-text-primary)" }}>
                                {criterion.name}
                              </span>
                              {criterion.mandatory ? (
                                <span
                                  style={{
                                    fontSize: "10px",
                                    fontWeight: 700,
                                    backgroundColor: "#fef2f2",
                                    color: "#991b1b",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    border: "1px solid #fca5a5",
                                  }}
                                >
                                  MANDATORY
                                </span>
                              ) : (
                                <span
                                  style={{
                                    fontSize: "10px",
                                    fontWeight: 600,
                                    backgroundColor: "#f3f4f6",
                                    color: "#4b5563",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                  }}
                                >
                                  OPTIONAL
                                </span>
                              )}
                            </div>
                            {criterion.description && (
                              <div style={{ fontSize: "12px", color: "var(--gov-text-secondary)", marginTop: "4px" }}>
                                {criterion.description}
                              </div>
                            )}
                            {criterion.required_evidence && (
                              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
                                <strong>Required Proof:</strong> {criterion.required_evidence}
                              </div>
                            )}
                          </div>

                          <div>
                            {matchedDoc ? (
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  fontSize: "11px",
                                  fontWeight: 700,
                                  color: "#059669",
                                  backgroundColor: "#d1fae5",
                                  padding: "3px 8px",
                                  borderRadius: "4px",
                                }}
                              >
                                ✓ UPLOADED
                              </span>
                            ) : (
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  color: criterion.mandatory ? "#b91c1c" : "#6b7280",
                                  backgroundColor: criterion.mandatory ? "#fee2e2" : "#f3f4f6",
                                  padding: "3px 8px",
                                  borderRadius: "4px",
                                }}
                              >
                                {criterion.mandatory ? "⚠ PENDING UPLOAD" : "○ NOT UPLOADED"}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Document Details or Upload Trigger */}
                        {matchedDoc ? (
                          <div
                            style={{
                              backgroundColor: "#ffffff",
                              borderRadius: "6px",
                              border: "1px solid #a7f3d0",
                              padding: "12px 16px",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: "10px",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              <div style={{ fontSize: "24px" }}>📄</div>
                              <div>
                                <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827" }}>
                                  {matchedDoc.filename}
                                </div>
                                <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
                                  {formatBytes(matchedDoc.file_size)} • Uploaded{" "}
                                  {new Date(matchedDoc.created_at).toLocaleString("en-IN", {
                                    timeZone: "Asia/Kolkata",
                                    day: "2-digit",
                                    month: "short",
                                    year: "numeric",
                                    hour: "2-digit",
                                    minute: "2-digit",
                                    hour12: true,
                                  })}{" "}
                                  IST
                                </div>
                              </div>
                            </div>

                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDownload(matchedDoc)}
                                disabled={downloadingDocId === matchedDoc.id}
                              >
                                {downloadingDocId === matchedDoc.id ? "Downloading..." : "View / Download 📥"}
                              </Button>

                              {isEditable && (
                                <>
                                  <label style={{ cursor: "pointer", margin: 0 }}>
                                    <input
                                      type="file"
                                      accept=".pdf,.doc,.docx,.xlsx,.jpg,.jpeg,.png"
                                      disabled={isUploadingThis}
                                      onChange={(e) => {
                                        const file = e.target.files?.[0];
                                        if (file) handleFileUpload(file, criterion.id);
                                        e.target.value = "";
                                      }}
                                      style={{ display: "none" }}
                                    />
                                    <span
                                      className="gov-btn gov-btn-outline gov-btn-sm"
                                      style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        pointerEvents: isUploadingThis ? "none" : "auto",
                                        opacity: isUploadingThis ? 0.6 : 1,
                                      }}
                                    >
                                      {isUploadingThis ? "Uploading..." : "Replace"}
                                    </span>
                                  </label>

                                  <Button
                                    variant="danger"
                                    size="sm"
                                    onClick={() => setDocumentToDelete(matchedDoc)}
                                    disabled={isUploadingThis}
                                  >
                                    Remove
                                  </Button>
                                </>
                              )}
                            </div>
                          </div>
                        ) : (
                          <div>
                            {isEditable ? (
                              <label
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  padding: "16px",
                                  border: "2px dashed var(--gov-border)",
                                  borderRadius: "6px",
                                  backgroundColor: "#ffffff",
                                  cursor: isUploadingThis ? "wait" : "pointer",
                                  transition: "border-color 0.2s",
                                }}
                              >
                                <input
                                  type="file"
                                  accept=".pdf,.doc,.docx,.xlsx,.jpg,.jpeg,.png"
                                  disabled={isUploadingThis}
                                  onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    if (file) handleFileUpload(file, criterion.id);
                                    e.target.value = "";
                                  }}
                                  style={{ display: "none" }}
                                />
                                <div style={{ fontSize: "20px", marginBottom: "4px" }}>
                                  {isUploadingThis ? "⏳" : "📤"}
                                </div>
                                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--gov-primary)" }}>
                                  {isUploadingThis ? "Validating & Uploading File..." : "Click to select file or drag and drop"}
                                </div>
                                <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
                                  PDF, Word (DOC/DOCX), Excel (XLSX), or JPEG/PNG up to 50 MB
                                </div>
                              </label>
                            ) : (
                              <div
                                style={{
                                  padding: "10px 14px",
                                  backgroundColor: "var(--gov-surface-secondary)",
                                  borderRadius: "6px",
                                  fontSize: "12px",
                                  color: "var(--gov-text-muted)",
                                }}
                              >
                                🔒 Upload disabled — application is sealed or submission window is closed.
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </CardContent>
            </Card>

            {/* General Supporting Documents Card */}
            <Card>
              <CardHeader>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <CardTitle style={{ fontSize: "16px" }}>
                      General Supporting Attachments & Certificates
                    </CardTitle>
                    <CardDescription>
                      Upload any supplementary vendor credentials, power of attorney, audited financials, or annexures.
                    </CardDescription>
                  </div>
                  {isEditable && (
                    <div>
                      <input
                        type="file"
                        ref={generalFileInputRef}
                        accept=".pdf,.doc,.docx,.xlsx,.jpg,.jpeg,.png"
                        disabled={isUploadingGeneral}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) handleFileUpload(file);
                          e.target.value = "";
                        }}
                        style={{ display: "none" }}
                      />
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => generalFileInputRef.current?.click()}
                        disabled={isUploadingGeneral}
                      >
                        {isUploadingGeneral ? "Uploading..." : "+ Upload Supporting Document"}
                      </Button>
                    </div>
                  )}
                </div>
              </CardHeader>

              <CardContent>
                {generalDocuments.length === 0 ? (
                  <div style={{ padding: "12px 0", fontSize: "13px", color: "var(--gov-text-muted)" }}>
                    No general supporting documents uploaded.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {generalDocuments.map((doc: BidderDocument) => (
                      <div
                        key={doc.id}
                        style={{
                          backgroundColor: "var(--gov-surface-secondary)",
                          borderRadius: "6px",
                          border: "1px solid var(--gov-border)",
                          padding: "10px 16px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          flexWrap: "wrap",
                          gap: "8px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <div style={{ fontSize: "20px" }}>📎</div>
                          <div>
                            <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--gov-text-primary)" }}>
                              {doc.filename}
                            </div>
                            <div style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                              {formatBytes(doc.file_size)} • Uploaded{" "}
                              {new Date(doc.created_at).toLocaleString("en-IN", {
                                timeZone: "Asia/Kolkata",
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                              })}
                            </div>
                          </div>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDownload(doc)}
                            disabled={downloadingDocId === doc.id}
                          >
                            {downloadingDocId === doc.id ? "Downloading..." : "Download 📥"}
                          </Button>
                          {isEditable && (
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => setDocumentToDelete(doc)}
                            >
                              Remove
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Commercial Bid & Compliance Declaration Form */}
            <Card>
              <CardHeader>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <CardTitle style={{ fontSize: "16px" }}>
                      {isSubmitted ? "Submitted Commercial Offer (Read-Only)" : "Commercial Offer & Statutory Declaration"}
                    </CardTitle>
                    <CardDescription>
                      {isSubmitted
                        ? "This information was officially sealed at the time of submission and is locked."
                        : "Review your commercial offer and affirm statutory compliance before final submission."}
                    </CardDescription>
                  </div>
                  {isSubmitted && (
                    <span style={{ fontSize: "12px", color: "var(--gov-text-muted)", fontWeight: 600 }}>
                      🔒 Locked for evaluation
                    </span>
                  )}
                </div>
              </CardHeader>

              <CardContent style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                {/* Commercial Quote */}
                <div>
                  <label
                    htmlFor="commercial-quote-input"
                    style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px", color: "var(--gov-text-primary)" }}
                  >
                    Total Proposed Commercial Bid (INR ₹)
                  </label>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "16px", fontWeight: 700, color: "var(--gov-text-muted)" }}>₹</span>
                    <input
                      id="commercial-quote-input"
                      type="number"
                      step="0.01"
                      min="0"
                      disabled={!isEditable}
                      value={commercialQuote}
                      onChange={(e) => setCommercialQuote(e.target.value)}
                      placeholder="e.g. 4500000"
                      style={{
                        padding: "8px 12px",
                        fontSize: "14px",
                        borderRadius: "6px",
                        border: "1px solid var(--gov-border)",
                        backgroundColor: isEditable ? "#ffffff" : "var(--gov-surface-secondary)",
                        color: "var(--gov-text-primary)",
                        width: "260px",
                        fontWeight: 600,
                      }}
                    />
                    {commercialQuote && !isNaN(Number(commercialQuote)) && Number(commercialQuote) > 0 && (
                      <span style={{ fontSize: "13px", color: "var(--gov-text-muted)", marginLeft: "8px" }}>
                        (₹ {Number(commercialQuote).toLocaleString("en-IN", { maximumFractionDigits: 2 })})
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "4px" }}>
                    Enter total bid value inclusive of all applicable statutory duties and GST.
                  </div>
                </div>

                {/* Technical / Compliance Notes */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                    <label
                      htmlFor="bidder-notes-input"
                      style={{ fontSize: "13px", fontWeight: 600, color: "var(--gov-text-primary)" }}
                    >
                      Technical Compliance Remarks & Delivery Commitments
                    </label>
                    <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                      {bidderNotes.length} / 5000 characters
                    </span>
                  </div>
                  <textarea
                    id="bidder-notes-input"
                    rows={4}
                    maxLength={5000}
                    disabled={!isEditable}
                    value={bidderNotes}
                    onChange={(e) => setBidderNotes(e.target.value)}
                    placeholder="Describe delivery schedules, manufacturing certifications, warranty commitments, or any compliance clarifications..."
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      fontSize: "13px",
                      borderRadius: "6px",
                      border: "1px solid var(--gov-border)",
                      backgroundColor: isEditable ? "#ffffff" : "var(--gov-surface-secondary)",
                      color: "var(--gov-text-primary)",
                      lineHeight: 1.5,
                      fontFamily: "inherit",
                    }}
                  />
                </div>

                {/* Statutory Affirmation Checkbox */}
                <div
                  style={{
                    backgroundColor: "var(--gov-surface-secondary)",
                    padding: "16px",
                    borderRadius: "6px",
                    border: "1px solid var(--gov-border)",
                  }}
                >
                  <label
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "12px",
                      cursor: isEditable ? "pointer" : "not-allowed",
                      fontSize: "13px",
                      lineHeight: 1.5,
                      color: "var(--gov-text-primary)",
                    }}
                  >
                    <input
                      type="checkbox"
                      id="declaration-checkbox"
                      disabled={!isEditable}
                      checked={declarationSigned}
                      onChange={(e) => setDeclarationSigned(e.target.checked)}
                      style={{ marginTop: "3px", width: "16px", height: "16px", cursor: isEditable ? "pointer" : "not-allowed" }}
                    />
                    <div>
                      <strong>Statutory Affirmation & Compliance Declaration:</strong>
                      <div style={{ fontSize: "12px", color: "var(--gov-text-secondary)", marginTop: "2px" }}>
                        I hereby solemnly declare and affirm that the technical and commercial details provided herein are true, accurate, and in strict compliance with the Request for Proposal (RFP) conditions. I acknowledge that once submitted, this bid is permanently sealed and subject to evaluation and integrity checks under the Public Procurement Act.
                      </div>
                    </div>
                  </label>
                </div>

                {/* Action Controls */}
                {isEditable && (
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "flex-end",
                      alignItems: "center",
                      gap: "12px",
                      paddingTop: "12px",
                      borderTop: "1px solid var(--gov-border)",
                    }}
                  >
                    <Button
                      variant="outline"
                      size="md"
                      onClick={handleSaveDraft}
                      disabled={isSaving || isSubmitting}
                    >
                      {isSaving ? "Saving Draft..." : "Save Draft"}
                    </Button>
                    <Button
                      variant="primary"
                      size="md"
                      onClick={() => {
                        if (!declarationSigned) {
                          setActionError("You must check and affirm the statutory compliance declaration before submitting.");
                          return;
                        }
                        setActionError(null);
                        setShowSubmitModal(true);
                      }}
                      disabled={isSaving || isSubmitting || isExpired}
                    >
                      Review & Submit Bid
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Document Removal Confirmation Modal */}
        {documentToDelete && (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-doc-modal-title"
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: "rgba(0, 0, 0, 0.5)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "20px",
            }}
          >
            <div
              style={{
                backgroundColor: "#ffffff",
                borderRadius: "8px",
                maxWidth: "480px",
                width: "100%",
                padding: "24px",
                boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.2)",
              }}
            >
              <h2 id="delete-doc-modal-title" style={{ fontSize: "17px", fontWeight: 700, margin: "0 0 10px 0", color: "#111827" }}>
                Remove Document?
              </h2>

              <p style={{ fontSize: "13px", color: "var(--gov-text-secondary)", lineHeight: 1.5, margin: "0 0 14px 0" }}>
                Are you sure you want to remove <strong>{documentToDelete.filename}</strong>?
              </p>

              <div
                style={{
                  backgroundColor: "#fef2f2",
                  border: "1px solid #fca5a5",
                  borderRadius: "6px",
                  padding: "12px",
                  marginBottom: "20px",
                  fontSize: "12px",
                  color: "#991b1b",
                  lineHeight: 1.4,
                }}
              >
                ⚠️ Removing this document will delete the stored binary and may mark the associated tender requirement as incomplete.
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => setDocumentToDelete(null)}
                  disabled={isDeleting}
                >
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  size="md"
                  onClick={handleConfirmDeleteDocument}
                  disabled={isDeleting}
                >
                  {isDeleting ? "Removing..." : "Confirm Removal"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Submission Confirmation Modal */}
        {showSubmitModal && (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="submit-modal-title"
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: "rgba(0, 0, 0, 0.5)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "20px",
            }}
          >
            <div
              style={{
                backgroundColor: "#ffffff",
                borderRadius: "8px",
                maxWidth: "540px",
                width: "100%",
                padding: "28px",
                boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.2)",
              }}
            >
              <h2 id="submit-modal-title" style={{ fontSize: "18px", fontWeight: 700, margin: "0 0 12px 0", color: "#111827" }}>
                Submit & Lock Bid Application?
              </h2>

              <p style={{ fontSize: "13px", color: "var(--gov-text-secondary)", lineHeight: 1.5, margin: "0 0 16px 0" }}>
                You are about to formally submit your bid response against tender <strong>{application?.tender_number}</strong>.
              </p>

              <div
                style={{
                  backgroundColor: "#fffbeb",
                  border: "1px solid #fde68a",
                  borderRadius: "6px",
                  padding: "14px",
                  marginBottom: "20px",
                  fontSize: "12px",
                  color: "#92400e",
                  lineHeight: 1.5,
                }}
              >
                <strong>⚠️ Irreversible Action:</strong> Once confirmed, this application and all {uploadedDocs.length} uploaded document(s) will be permanently sealed with an authoritative server timestamp and locked from editing, replacement, or deletion.
              </div>

              <div style={{ fontSize: "13px", color: "var(--gov-text-primary)", marginBottom: "24px" }}>
                <div style={{ marginBottom: "6px" }}>
                  • Quoted Value: <strong>{commercialQuote ? `₹ ${Number(commercialQuote).toLocaleString("en-IN")}` : "Unspecified"}</strong>
                </div>
                <div style={{ marginBottom: "6px" }}>
                  • Mandatory Documents: <strong>{mandatoryUploadedCount} of {mandatoryTotalCount} satisfied</strong>
                </div>
                <div style={{ marginBottom: "6px" }}>
                  • Total Documents: <strong>{uploadedDocs.length} file(s) attached</strong>
                </div>
                <div>
                  • Specification: <strong>v{application?.version_number} ({application?.version_label})</strong>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px" }}>
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => setShowSubmitModal(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  onClick={handleConfirmSubmit}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Submitting..." : "Confirm Final Submission"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </PageContainer>
    </AppShell>
  );
}

export default function ApplicationDetailPage() {
  return (
    <ProtectedRoute requiredPermission="BIDDER_READ">
      <ApplicationDetailContent />
    </ProtectedRoute>
  );
}
