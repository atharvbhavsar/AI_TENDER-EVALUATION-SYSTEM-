import React from "react";
import { Card, CardContent } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";

export interface SummaryCardProps {
  title: string;
  value?: number | string | null;
  subtitle?: string;
  icon?: React.ReactNode;
  statusBadge?: React.ReactNode;
  isLoading?: boolean;
  error?: string;
  onClick?: () => void;
  accentColor?: string;
}

export function SummaryCard({
  title,
  value,
  subtitle,
  icon,
  statusBadge,
  isLoading = false,
  error,
  onClick,
  accentColor = "var(--gov-primary)",
}: SummaryCardProps) {
  return (
    <Card
      style={{
        cursor: onClick ? "pointer" : "default",
        borderTop: `3px solid ${accentColor}`,
        transition: "transform 0.15s ease, box-shadow 0.15s ease",
      }}
      className={onClick ? "hover:shadow-md hover:-translate-y-0.5" : ""}
      onClick={onClick}
    >
      <CardContent style={{ padding: "18px 20px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
          <div>
            <div
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--gov-text-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: "6px",
              }}
            >
              {title}
            </div>

            {isLoading ? (
              <div style={{ margin: "8px 0" }}>
                <Skeleton width="60px" height="28px" />
              </div>
            ) : error ? (
              <div style={{ fontSize: "13px", color: "var(--status-danger-text)", fontWeight: 500, margin: "6px 0" }}>
                Data unavailable
              </div>
            ) : (
              <div
                style={{
                  fontSize: "26px",
                  fontWeight: 800,
                  color: "var(--gov-text-primary)",
                  lineHeight: 1.1,
                  letterSpacing: "-0.02em",
                }}
              >
                {value !== undefined && value !== null ? value : "0"}
              </div>
            )}

            {subtitle && (
              <div
                style={{
                  fontSize: "11px",
                  color: "var(--gov-text-muted)",
                  marginTop: "6px",
                  lineHeight: 1.3,
                }}
              >
                {subtitle}
              </div>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "6px" }}>
            {icon && (
              <div
                style={{
                  width: "38px",
                  height: "38px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "var(--gov-surface-secondary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "18px",
                  color: accentColor,
                  flexShrink: 0,
                }}
                aria-hidden="true"
              >
                {icon}
              </div>
            )}
            {statusBadge && <div>{statusBadge}</div>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
