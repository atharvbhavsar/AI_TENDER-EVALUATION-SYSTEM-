import React from "react";
import { Button } from "./Button";
import type { APIError } from "@/types/api";

export interface ErrorStateProps {
  title?: string;
  error?: string | APIError | null;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Failed to load data",
  error,
  onRetry,
  className = "",
}: ErrorStateProps) {
  let displayMessage = "An unexpected error occurred. Please try again.";
  let statusType: string | undefined;
  let statusCode: number | undefined;

  if (typeof error === "string") {
    displayMessage = error;
  } else if (error && typeof error === "object") {
    displayMessage = error.message || displayMessage;
    statusType = error.statusType;
    statusCode = error.statusCode;
  }

  return (
    <div
      role="alert"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 20px",
        textAlign: "center",
        backgroundColor: "var(--status-danger-bg)",
        border: "1px solid var(--status-danger-border)",
        borderRadius: "var(--radius-lg)",
      }}
      className={`gov-error-state ${className}`}
    >
      <div
        style={{
          width: "44px",
          height: "44px",
          borderRadius: "50%",
          backgroundColor: "#fee2e2",
          color: "#dc2626",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "20px",
          marginBottom: "14px",
          fontWeight: 700,
        }}
      >
        ✕
      </div>

      <h3
        style={{
          margin: "0 0 6px 0",
          fontSize: "15px",
          fontWeight: 600,
          color: "var(--status-danger-text)",
        }}
      >
        {title}
      </h3>

      <p
        style={{
          margin: "0 0 16px 0",
          fontSize: "13px",
          color: "#7f1d1d",
          maxWidth: "480px",
          lineHeight: 1.4,
        }}
      >
        {displayMessage}
      </p>

      {(statusType || (statusCode && statusCode > 0)) && (
        <div
          style={{
            fontSize: "11px",
            fontFamily: "var(--font-family-mono)",
            color: "#991b1b",
            backgroundColor: "#fecaca",
            padding: "2px 8px",
            borderRadius: "4px",
            marginBottom: "16px",
          }}
        >
          {statusType && <span>{statusType}</span>}
          {statusCode ? <span> (HTTP {statusCode})</span> : null}
        </div>
      )}

      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  );
}
