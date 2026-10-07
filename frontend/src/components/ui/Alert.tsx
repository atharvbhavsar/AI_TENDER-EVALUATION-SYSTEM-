import React from "react";

export interface AlertProps {
  variant?: "info" | "success" | "warning" | "danger";
  title?: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function Alert({
  variant = "info",
  title,
  children,
  icon,
  action,
  className = "",
}: AlertProps) {
  const configs: Record<
    string,
    { bg: string; text: string; border: string; defaultIcon: string }
  > = {
    info: {
      bg: "var(--status-info-bg)",
      text: "var(--status-info-text)",
      border: "var(--status-info-border)",
      defaultIcon: "ℹ",
    },
    success: {
      bg: "var(--status-success-bg)",
      text: "var(--status-success-text)",
      border: "var(--status-success-border)",
      defaultIcon: "✓",
    },
    warning: {
      bg: "var(--status-warning-bg)",
      text: "var(--status-warning-text)",
      border: "var(--status-warning-border)",
      defaultIcon: "⚠",
    },
    danger: {
      bg: "var(--status-danger-bg)",
      text: "var(--status-danger-text)",
      border: "var(--status-danger-border)",
      defaultIcon: "✕",
    },
  };

  const current = configs[variant];

  return (
    <div
      role="alert"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "12px",
        padding: "12px 16px",
        borderRadius: "var(--radius-md)",
        backgroundColor: current.bg,
        border: `1px solid ${current.border}`,
        color: current.text,
        fontSize: "13px",
      }}
      className={`gov-alert ${className}`}
    >
      <span
        aria-hidden="true"
        style={{
          fontWeight: 700,
          fontSize: "14px",
          lineHeight: 1.2,
          marginTop: "1px",
        }}
      >
        {icon || current.defaultIcon}
      </span>

      <div style={{ flex: 1, minWidth: 0 }}>
        {title && (
          <h4
            style={{
              margin: "0 0 2px 0",
              fontWeight: 600,
              fontSize: "13px",
              color: current.text,
            }}
          >
            {title}
          </h4>
        )}
        <div style={{ lineHeight: 1.4 }}>{children}</div>
      </div>

      {action && <div style={{ flexShrink: 0 }}>{action}</div>}
    </div>
  );
}
