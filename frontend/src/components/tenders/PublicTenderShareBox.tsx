"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

export interface PublicTenderShareBoxProps {
  tenderId: string;
  tenderNumber: string;
}

export function PublicTenderShareBox({ tenderId, tenderNumber }: PublicTenderShareBoxProps) {
  const [copied, setCopied] = useState(false);

  const publicPath = `/tenders/public/${tenderId}`;

  const handleCopyLink = async () => {
    try {
      const fullUrl = typeof window !== "undefined" ? `${window.location.origin}${publicPath}` : publicPath;
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch {
      // Fallback
    }
  };

  return (
    <div
      style={{
        padding: "16px 20px",
        backgroundColor: "var(--status-success-bg)",
        border: "1px solid var(--status-success-border)",
        borderRadius: "var(--radius-lg)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "50%",
            backgroundColor: "#dcfce7",
            color: "#166534",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "18px",
            fontWeight: 700,
          }}
          aria-hidden="true"
        >
          🌐
        </div>

        <div>
          <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--status-success-text)" }}>
            Tender Published & Publicly Available
          </div>
          <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
            Reference: <strong>{tenderNumber}</strong> • Accessible to all prospective bidders without authentication.
          </div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <Button variant="outline" size="sm" onClick={handleCopyLink}>
          {copied ? "✓ Copied!" : "📋 Copy Public Link"}
        </Button>

        <Link href={publicPath} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>
          <Button variant="primary" size="sm" style={{ backgroundColor: "#166534" }}>
            Preview Public Portal ↗
          </Button>
        </Link>
      </div>
    </div>
  );
}
