import React from "react";
import Link from "next/link";
import { Button, Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui";

export interface AccessDeniedProps {
  title?: string;
  message?: string;
  requiredPermission?: string;
  requiredRole?: string;
}

export function AccessDenied({
  title = "Access Restricted",
  message = "You do not have the required administrative or officer permissions to access this procurement module.",
  requiredPermission,
  requiredRole,
}: AccessDeniedProps) {
  return (
    <div style={{ maxWidth: "560px", margin: "40px auto", width: "100%" }}>
      <Card>
        <CardHeader>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
            <span
              style={{
                backgroundColor: "var(--status-danger-bg)",
                color: "var(--status-danger-text)",
                border: "1px solid var(--status-danger-border)",
                fontWeight: 700,
                padding: "2px 6px",
                borderRadius: "4px",
                fontSize: "11px",
              }}
            >
              HTTP 403 FORBIDDEN
            </span>
            <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
              Role-Based Authorization Enforcement
            </span>
          </div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{message}</CardDescription>
        </CardHeader>

        {(requiredPermission || requiredRole) && (
          <CardContent>
            <div
              style={{
                padding: "12px",
                borderRadius: "var(--radius-md)",
                backgroundColor: "var(--gov-surface-secondary)",
                fontSize: "12px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
              }}
            >
              <div style={{ fontWeight: 600, color: "var(--gov-text-secondary)" }}>
                Required Authorization Clearance:
              </div>
              {requiredRole && (
                <div>
                  Role: <code style={{ color: "var(--gov-primary)", fontWeight: 600 }}>{requiredRole}</code>
                </div>
              )}
              {requiredPermission && (
                <div>
                  Permission: <code style={{ color: "var(--gov-primary)", fontWeight: 600 }}>{requiredPermission}</code>
                </div>
              )}
            </div>
          </CardContent>
        )}

        <CardFooter>
          <div style={{ display: "flex", justifyContent: "flex-end", width: "100%" }}>
            <Link href="/dashboard" style={{ textDecoration: "none" }}>
              <Button variant="primary" size="md">
                Return to Dashboard
              </Button>
            </Link>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
