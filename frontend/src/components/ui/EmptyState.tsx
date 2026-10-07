import React from "react";

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "48px 24px",
        textAlign: "center",
        backgroundColor: "var(--gov-surface)",
        border: "1px dashed var(--gov-border-strong)",
        borderRadius: "var(--radius-lg)",
      }}
      className={`gov-empty-state ${className}`}
    >
      <div
        style={{
          width: "48px",
          height: "48px",
          borderRadius: "50%",
          backgroundColor: "var(--gov-surface-secondary)",
          color: "var(--gov-text-muted)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "22px",
          marginBottom: "16px",
        }}
      >
        {icon || "📄"}
      </div>

      <h3
        style={{
          margin: "0 0 6px 0",
          fontSize: "15px",
          fontWeight: 600,
          color: "var(--gov-text-primary)",
        }}
      >
        {title}
      </h3>

      {description && (
        <p
          style={{
            margin: "0 0 16px 0",
            fontSize: "13px",
            color: "var(--gov-text-muted)",
            maxWidth: "400px",
            lineHeight: 1.4,
          }}
        >
          {description}
        </p>
      )}

      {action && <div>{action}</div>}
    </div>
  );
}
