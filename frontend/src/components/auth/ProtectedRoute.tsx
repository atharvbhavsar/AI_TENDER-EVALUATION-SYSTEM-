"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { AccessDenied } from "./AccessDenied";
import { AppShell, PageContainer } from "@/components/layout";
import { Spinner } from "@/components/ui";
import type { PermissionName, RoleName } from "@/types/auth";

export interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermission?: PermissionName;
  requiredPermissions?: PermissionName[];
  requiredRole?: RoleName;
  requiredRoles?: RoleName[];
}

export function ProtectedRoute({
  children,
  requiredPermission,
  requiredPermissions,
  requiredRole,
  requiredRoles,
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, hasPermission, hasRole, hasAnyPermission } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const returnUrl = pathname ? encodeURIComponent(pathname) : "";
      router.push(`/login${returnUrl ? `?returnUrl=${returnUrl}` : ""}`);
    }
  }, [isLoading, isAuthenticated, router, pathname]);

  // Loading state prevents flashing unauthenticated UI during initialization
  if (isLoading) {
    return (
      <AppShell>
        <PageContainer maxWidth="xl">
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              minHeight: "400px",
              gap: "12px",
            }}
          >
            <Spinner size="lg" />
            <span style={{ fontSize: "13px", color: "var(--gov-text-muted)" }}>
              Verifying security credentials and role clearance...
            </span>
          </div>
        </PageContainer>
      </AppShell>
    );
  }

  // Not authenticated: effect will handle redirect; render neutral loading placeholder
  if (!isAuthenticated) {
    return null;
  }

  // Check required permission
  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <AppShell>
        <PageContainer maxWidth="lg">
          <AccessDenied
            title="Module Access Restricted"
            message="Your account does not possess the requisite permission to access this procurement module."
            requiredPermission={requiredPermission}
          />
        </PageContainer>
      </AppShell>
    );
  }

  // Check list of required permissions
  if (requiredPermissions && requiredPermissions.length > 0 && !hasAnyPermission(requiredPermissions)) {
    return (
      <AppShell>
        <PageContainer maxWidth="lg">
          <AccessDenied
            title="Module Access Restricted"
            message="Your account lacks at least one required permission to access this section."
            requiredPermission={requiredPermissions.join(" OR ")}
          />
        </PageContainer>
      </AppShell>
    );
  }

  // Check required role
  if (requiredRole && !hasRole(requiredRole)) {
    return (
      <AppShell>
        <PageContainer maxWidth="lg">
          <AccessDenied
            title="Restricted by Officer Role"
            message={`This administrative module is restricted to users holding the ${requiredRole} role.`}
            requiredRole={requiredRole}
          />
        </PageContainer>
      </AppShell>
    );
  }

  // Check list of required roles
  if (requiredRoles && requiredRoles.length > 0) {
    const hasAnyRole = requiredRoles.some((r) => hasRole(r));
    if (!hasAnyRole) {
      return (
        <AppShell>
          <PageContainer maxWidth="lg">
            <AccessDenied
              title="Restricted by Officer Role"
              message={`This module requires one of the following roles: ${requiredRoles.join(", ")}.`}
              requiredRole={requiredRoles.join(" / ")}
            />
          </PageContainer>
        </AppShell>
      );
    }
  }

  return <>{children}</>;
}
