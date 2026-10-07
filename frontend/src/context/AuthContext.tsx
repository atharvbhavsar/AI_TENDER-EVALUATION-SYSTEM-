"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { fetchCurrentUser, loginUser, logoutUser, registerBidder } from "@/lib/api/auth";
import { hasAccessToken } from "@/lib/api/token";
import { setOnUnauthorizedHandler } from "@/lib/api/client";
import type { AuthContextType, LoginRequest, PermissionName, RegisterBidderRequest, RoleName, UserResponse } from "@/types/auth";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    logoutUser();
    setCurrentUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!hasAccessToken()) {
      setCurrentUser(null);
      return;
    }
    try {
      const user = await fetchCurrentUser();
      setCurrentUser(user);
    } catch {
      logout();
    }
  }, [logout]);

  const login = useCallback(async (credentials: LoginRequest) => {
    setIsLoading(true);
    try {
      await loginUser(credentials);
      const user = await fetchCurrentUser();
      setCurrentUser(user);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (data: RegisterBidderRequest) => {
    setIsLoading(true);
    try {
      await registerBidder(data);
      const user = await fetchCurrentUser();
      setCurrentUser(user);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Register 401 handler on client initialization
  useEffect(() => {
    setOnUnauthorizedHandler(() => {
      logout();
    });

    let isMounted = true;

    async function initAuth() {
      if (hasAccessToken()) {
        try {
          const user = await fetchCurrentUser();
          if (isMounted) {
            setCurrentUser(user);
          }
        } catch {
          if (isMounted) {
            logout();
          }
        }
      }
      if (isMounted) {
        setIsLoading(false);
      }
    }

    initAuth();

    return () => {
      isMounted = false;
    };
  }, [logout]);

  const hasPermission = useCallback(
    (permission: PermissionName): boolean => {
      if (!currentUser?.permissions) return false;
      return currentUser.permissions.includes(permission);
    },
    [currentUser]
  );

  const hasRole = useCallback(
    (role: RoleName): boolean => {
      if (!currentUser?.roles) return false;
      return currentUser.roles.includes(role);
    },
    [currentUser]
  );

  const hasAnyPermission = useCallback(
    (permissions: PermissionName[]): boolean => {
      if (!currentUser?.permissions) return false;
      return permissions.some((p) => currentUser.permissions.includes(p));
    },
    [currentUser]
  );

  const hasAllPermissions = useCallback(
    (permissions: PermissionName[]): boolean => {
      if (!currentUser?.permissions) return false;
      return permissions.every((p) => currentUser.permissions.includes(p));
    },
    [currentUser]
  );

  const contextValue: AuthContextType = {
    currentUser,
    isAuthenticated: Boolean(currentUser),
    isLoading,
    login,
    register,
    logout,
    refreshUser,
    hasPermission,
    hasRole,
    hasAnyPermission,
    hasAllPermissions,
  };

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
