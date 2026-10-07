"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { createTender, type TenderItem, type CreateTenderPayload } from "@/lib/api/tenders";

export interface CreateTenderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTenderCreated: (newTender: TenderItem) => void;
}

export function CreateTenderModal({
  isOpen,
  onClose,
  onTenderCreated,
}: CreateTenderModalProps) {
  const [formData, setFormData] = useState<CreateTenderPayload>({
    tender_number: "",
    title: "",
    description: "",
    issuing_authority: "CRPF Procurement Directorate",
    initial_version_label: "Original Release",
    initial_change_summary: "Initial Draft Creation",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.tender_number.trim() || !formData.title.trim()) {
      setError("Tender number and title are required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const created = await createTender(formData);
      onTenderCreated(created);
      onClose();
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to create draft tender.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-tender-modal-title"
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
          maxWidth: "560px",
          backgroundColor: "#ffffff",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-lg)",
          border: "1px solid var(--gov-border)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
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
            <span style={{ fontSize: "18px" }}>📝</span>
            <h3 id="create-tender-modal-title" style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>
              Create New Procurement Tender (Draft)
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
            }}
          >
            ✕
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit}>
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: "14px" }}>
            {error && (
              <Alert variant="danger" title="Creation Error">
                {error}
              </Alert>
            )}

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                Tender Number / Reference ID *
              </label>
              <Input
                type="text"
                required
                placeholder="e.g. CRPF/PPE/2026/002"
                value={formData.tender_number}
                onChange={(e) => setFormData({ ...formData, tender_number: e.target.value })}
              />
              <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                Must be a unique procurement reference number.
              </span>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                Tender Title / Procurement Scope *
              </label>
              <Input
                type="text"
                required
                placeholder="e.g. Supply of Lightweight Ballistic Helmets"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                Issuing Directorate / Wing
              </label>
              <Input
                type="text"
                placeholder="e.g. CRPF Procurement Directorate, New Delhi"
                value={formData.issuing_authority}
                onChange={(e) => setFormData({ ...formData, issuing_authority: e.target.value })}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                Description & Technical Specifications
              </label>
              <textarea
                rows={3}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                  fontSize: "13px",
                  fontFamily: "inherit",
                }}
                placeholder="Detailed procurement specifications, scope of work, and delivery timelines..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
          </div>

          {/* Footer */}
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
            <Button variant="outline" size="sm" type="button" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" isLoading={isSubmitting}>
              Create Draft Tender
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
