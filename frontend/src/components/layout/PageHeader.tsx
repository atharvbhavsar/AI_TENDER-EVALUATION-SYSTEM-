import React from "react";
import { Breadcrumbs, BreadcrumbItem } from "./Breadcrumbs";

export interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  showBreadcrumbs?: boolean;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  showBreadcrumbs = true,
  badge,
  actions,
  className = "",
}: PageHeaderProps) {
  return (
    <header
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        marginBottom: "24px",
      }}
      className={`gov-page-header ${className}`}
    >
      {showBreadcrumbs && <Breadcrumbs items={breadcrumbs} />}

      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxWidth: "800px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <h1
              style={{
                margin: 0,
                fontSize: "22px",
                fontWeight: 700,
                color: "var(--gov-text-primary)",
                letterSpacing: "-0.02em",
                lineHeight: 1.2,
              }}
            >
              {title}
            </h1>
            {badge && <div>{badge}</div>}
          </div>

          {description && (
            <p
              style={{
                margin: "4px 0 0 0",
                fontSize: "13px",
                color: "var(--gov-text-secondary)",
                lineHeight: 1.4,
              }}
            >
              {description}
            </p>
          )}
        </div>

        {actions && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              flexShrink: 0,
            }}
          >
            {actions}
          </div>
        )}
      </div>
    </header>
  );
}
