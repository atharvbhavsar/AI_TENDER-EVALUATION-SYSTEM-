"use client";

import React from "react";
import { useAuth } from "@/context/AuthContext";
import type { PermissionName, RoleName } from "@/types/auth";

export interface PermissionGateProps {
  children: React.ReactNode;
  permission?: PermissionName;
  permissions?: PermissionName[];
  role?: RoleName;
  roles?: RoleName[];
  requireAll?: boolean;
  fallback?: React.ReactNode;
}

export function PermissionGate({
  children,
  permission,
  permissions,
  role,
  roles,
  requireAll = false,
  fallback = null,
}: PermissionGateProps) {
  const { hasPermission, hasRole, hasAnyPermission, hasAllPermissions, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <>{fallback}</>;
  }

  // Check specific permission
  if (permission && !hasPermission(permission)) {
    return <>{fallback}</>;
  }

  // Check list of permissions
  if (permissions && permissions.length > 0) {
    const isAllowed = requireAll ? hasAllPermissions(permissions) : hasAnyPermission(permissions);
    if (!isAllowed) {
      return <>{fallback}</>;
    }
  }

  // Check specific role
  if (role && !hasRole(role)) {
    return <>{fallback}</>;
  }

  // Check list of roles
  if (roles && roles.length > 0) {
    const isAllowed = roles.some((r) => hasRole(r));
    if (!isAllowed) {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}
