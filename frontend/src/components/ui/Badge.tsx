import React from "react";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info" | "neutral";
  size?: "sm" | "md";
  className?: string;
  icon?: React.ReactNode;
}

export function Badge({
  children,
  variant = "default",
  size = "md",
  className = "",
  icon,
}: BadgeProps) {
  const variantStyles: Record<string, React.CSSProperties> = {
    default: {
      backgroundColor: "var(--gov-surface-secondary)",
      color: "var(--gov-text-secondary)",
      border: "1px solid var(--gov-border-strong)",
    },
    success: {
      backgroundColor: "var(--status-success-bg)",
      color: "var(--status-success-text)",
      border: "1px solid var(--status-success-border)",
    },
    warning: {
      backgroundColor: "var(--status-warning-bg)",
      color: "var(--status-warning-text)",
      border: "1px solid var(--status-warning-border)",
    },
    danger: {
      backgroundColor: "var(--status-danger-bg)",
      color: "var(--status-danger-text)",
      border: "1px solid var(--status-danger-border)",
    },
    info: {
      backgroundColor: "var(--status-info-bg)",
      color: "var(--status-info-text)",
      border: "1px solid var(--status-info-border)",
    },
    neutral: {
      backgroundColor: "var(--status-neutral-bg)",
      color: "var(--status-neutral-text)",
      border: "1px solid var(--status-neutral-border)",
    },
  };

  const isSmall = size === "sm";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: isSmall ? "2px 6px" : "3px 8px",
        fontSize: isSmall ? "11px" : "12px",
        fontWeight: 600,
        borderRadius: "4px",
        lineHeight: 1.2,
        letterSpacing: "0.02em",
        ...variantStyles[variant],
      }}
      className={className}
    >
      {icon && <span style={{ display: "inline-flex" }}>{icon}</span>}
      <span>{children}</span>
    </span>
  );
}
