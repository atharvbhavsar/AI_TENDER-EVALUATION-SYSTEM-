import React from "react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  badge,
  actions,
  className = "",
}: PageHeaderProps) {
  return (
    <header
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        marginBottom: "24px",
      }}
      className={`gov-page-header ${className}`}
    >
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" style={{ fontSize: "12px", color: "var(--gov-text-muted)" }}>
          <ol style={{ display: "flex", alignItems: "center", gap: "6px", margin: 0, padding: 0, listStyle: "none" }}>
            {breadcrumbs.map((crumb, idx) => (
              <li key={idx} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                {idx > 0 && <span aria-hidden="true" style={{ opacity: 0.5 }}>/</span>}
                {crumb.href ? (
                  <a
                    href={crumb.href}
                    style={{ color: "var(--gov-text-secondary)", textDecoration: "none" }}
                  >
                    {crumb.label}
                  </a>
                ) : (
                  <span style={{ color: "var(--gov-text-primary)", fontWeight: 500 }} aria-current="page">
                    {crumb.label}
                  </span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1
              style={{
                margin: 0,
                fontSize: "22px",
                fontWeight: 700,
                color: "var(--gov-text-primary)",
                letterSpacing: "-0.02em",
              }}
            >
              {title}
            </h1>
            {badge && <div>{badge}</div>}
          </div>
          {description && (
            <p
              style={{
                margin: 0,
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
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
            {actions}
          </div>
        )}
      </div>
    </header>
  );
}
