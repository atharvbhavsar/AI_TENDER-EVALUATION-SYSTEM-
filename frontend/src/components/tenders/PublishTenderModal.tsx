"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { TenderItem } from "@/lib/api/tenders";

export interface PublishTenderModalProps {
  tender: TenderItem;
  isOpen: boolean;
  onClose: () => void;
  onConfirmPublish: () => Promise<void>;
}

export function PublishTenderModal({
  tender,
  isOpen,
  onClose,
  onConfirmPublish,
}: PublishTenderModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen && !isSubmitting) {
        onClose();
      }
    }
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, isSubmitting, onClose]);

  if (!isOpen) return null;

  const handlePublish = async () => {
    setIsSubmitting(true);
    setPublishError(null);
    try {
      await onConfirmPublish();
      onClose();
    } catch (err: unknown) {
      setPublishError((err as Error).message || "Publishing failed. Please check tender requirements.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="publish-modal-title"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(11, 37, 69, 0.6)",
        backdropFilter: "blur(2px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: "16px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "520px",
          backgroundColor: "#ffffff",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-lg)",
          border: "1px solid var(--gov-border)",
          overflow: "hidden",
          animation: "gov-pulse 0.15s ease-out",
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            backgroundColor: "var(--gov-primary)",
            color: "#ffffff",
            padding: "16px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "18px" }} aria-hidden="true">📢</span>
            <h3 id="publish-modal-title" style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>
              Publish Procurement Tender
            </h3>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close dialog"
            style={{
              background: "none",
              border: "none",
              color: "#ffffff",
              fontSize: "18px",
              cursor: "pointer",
              lineHeight: 1,
              padding: "4px",
            }}
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ fontSize: "13px", color: "var(--gov-text-secondary)", lineHeight: 1.5 }}>
            You are about to officially transition this tender notice to <strong>PUBLISHED</strong> status.
            Once published, it will be immediately discoverable on the <strong>Public Tender Portal</strong> without requiring officer login.
          </div>

          {/* Tender Summary Details Box */}
          <div
            style={{
              padding: "12px 16px",
              backgroundColor: "var(--gov-surface-secondary)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--gov-border)",
              fontSize: "12px",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--gov-text-muted)" }}>Tender Number:</span>
              <strong style={{ color: "var(--gov-primary)" }}>{tender.tender_number}</strong>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--gov-text-muted)" }}>Title:</span>
              <span style={{ fontWeight: 600, color: "var(--gov-text-primary)", textAlign: "right", maxWidth: "280px" }}>
                {tender.title}
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--gov-text-muted)" }}>Issuing Authority:</span>
              <span style={{ color: "var(--gov-text-secondary)" }}>{tender.issuing_authority}</span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "var(--gov-text-muted)" }}>Current Lifecycle:</span>
              <StatusBadge status={tender.status} size="sm" />
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--gov-text-muted)" }}>Active Specification:</span>
              <span style={{ fontWeight: 600, color: "var(--gov-text-secondary)" }}>
                {tender.active_version ? `v${tender.active_version.version_number} (${tender.active_version.version_label})` : "Version 1"}
              </span>
            </div>
          </div>

          {/* Warning Alert */}
          <Alert variant="warning" title="Regulatory Notice">
            After publishing, bidders can view technical requirements and download published specifications. Corrigenda must be issued through new version releases.
          </Alert>

          {publishError && (
            <Alert variant="danger" title="Publishing Failed">
              {publishError}
            </Alert>
          )}
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: "12px 24px",
            backgroundColor: "var(--gov-surface-secondary)",
            borderTop: "1px solid var(--gov-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "12px",
          }}
        >
          <Button variant="outline" size="sm" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>

          <Button
            variant="primary"
            size="sm"
            isLoading={isSubmitting}
            onClick={handlePublish}
            style={{ backgroundColor: "#166534" }}
          >
            Confirm & Publish Tender
          </Button>
        </div>
      </div>
    </div>
  );
}
