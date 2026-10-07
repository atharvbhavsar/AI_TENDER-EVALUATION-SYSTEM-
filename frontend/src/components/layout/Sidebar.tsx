"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { NAVIGATION_GROUPS, BIDDER_NAVIGATION_GROUPS, isRouteActive } from "@/config/navigation";
import { NavIcon } from "./NavIcons";

export interface SidebarProps {
  isMobileOpen?: boolean;
  onMobileClose?: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function Sidebar({
  isMobileOpen = false,
  onMobileClose,
  isCollapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  const pathname = usePathname();
  const { isAuthenticated, hasPermission, hasRole } = useAuth();

  const isBidder = hasRole("BIDDER") && !hasRole("ADMIN") && !hasRole("PROCUREMENT_OFFICER");
  const targetGroups = isBidder ? BIDDER_NAVIGATION_GROUPS : NAVIGATION_GROUPS;

  // Filter groups and items based on authentication & permissions
  const filteredGroups = targetGroups.map((group) => {
    const permittedItems = group.items.filter((item) => {
      if (!isAuthenticated && item.requiredPermission) return false;
      if (item.requiredPermission && !hasPermission(item.requiredPermission)) return false;
      if (item.requiredRole && !hasRole(item.requiredRole)) return false;
      return true;
    });

    return {
      ...group,
      items: permittedItems,
    };
  }).filter((group) => group.items.length > 0);

  const sidebarWidth = isCollapsed ? "68px" : "250px";

  return (
    <>
      {/* Mobile Backdrop */}
      <div
        onClick={onMobileClose}
        aria-hidden="true"
        className={`sidebar-backdrop ${isMobileOpen ? "is-open" : ""}`}
        style={{
          position: "fixed",
          inset: 0,
          backgroundColor: "rgba(0, 0, 0, 0.4)",
          zIndex: 40,
          display: "none",
        }}
      />

      <aside
        aria-label="Application Sidebar Navigation"
        style={{
          width: sidebarWidth,
          transition: "width 0.2s ease-in-out",
          backgroundColor: "#ffffff",
          borderRight: "1px solid var(--gov-border)",
          display: "flex",
          flexDirection: "column",
          flexShrink: 0,
          minHeight: "calc(100vh - 56px)",
          padding: "16px 0",
        }}
        className={`gov-sidebar ${isMobileOpen ? "is-open" : ""}`}
      >
        <nav
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "16px",
            flex: 1,
            padding: isCollapsed ? "0 8px" : "0 12px",
          }}
        >
          {filteredGroups.map((group) => (
            <div key={group.id} style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              {/* Group Title or Collapsed Divider */}
              {!isCollapsed ? (
                <div
                  style={{
                    padding: "4px 10px 6px 10px",
                    fontSize: "11px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "var(--gov-text-muted)",
                  }}
                >
                  {group.title}
                </div>
              ) : (
                <div
                  style={{
                    height: "1px",
                    backgroundColor: "var(--gov-border)",
                    margin: "8px 4px",
                  }}
                  aria-hidden="true"
                />
              )}

              {/* Group Items */}
              {group.items.map((item) => {
                const isActive = isRouteActive(item.href, pathname, item.exactMatch);

                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    onClick={onMobileClose}
                    aria-current={isActive ? "page" : undefined}
                    aria-label={isCollapsed ? item.label : undefined}
                    title={isCollapsed ? item.label : undefined}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: isCollapsed ? "center" : "space-between",
                      padding: isCollapsed ? "10px 0" : "8px 12px",
                      borderRadius: "var(--radius-md)",
                      fontSize: "13px",
                      fontWeight: isActive ? 600 : 500,
                      color: isActive ? "var(--gov-primary)" : "var(--gov-text-secondary)",
                      backgroundColor: isActive ? "var(--status-info-bg)" : "transparent",
                      borderLeft: isCollapsed
                        ? "none"
                        : isActive
                        ? "3px solid var(--gov-primary)"
                        : "3px solid transparent",
                      border: isCollapsed && isActive ? "1px solid var(--status-info-border)" : undefined,
                      textDecoration: "none",
                      transition: "all 0.15s ease",
                    }}
                    className="gov-nav-link"
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          color: isActive ? "var(--gov-primary)" : "var(--gov-text-muted)",
                        }}
                      >
                        <NavIcon name={item.iconName} size={18} />
                      </span>
                      {!isCollapsed && <span>{item.label}</span>}
                    </div>

                    {!isCollapsed && item.badge && (
                      <span
                        style={{
                          fontSize: "11px",
                          padding: "1px 6px",
                          borderRadius: "10px",
                          backgroundColor: "var(--gov-surface-secondary)",
                          color: "var(--gov-text-muted)",
                        }}
                      >
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Sidebar Footer & Collapse Toggle Button */}
        <div
          style={{
            marginTop: "auto",
            padding: isCollapsed ? "12px 8px 0 8px" : "16px 12px 0 12px",
            borderTop: "1px solid var(--gov-border)",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          {!isCollapsed && (
            <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", padding: "0 6px" }}>
              <div style={{ fontWeight: 600, color: "var(--gov-text-secondary)" }}>
                CRPF Tender System
              </div>
              <div>Deterministic OPA Engine</div>
            </div>
          )}

          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              aria-label={isCollapsed ? "Expand sidebar navigation" : "Collapse sidebar navigation"}
              title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: isCollapsed ? "center" : "flex-start",
                gap: "8px",
                padding: "8px 10px",
                width: "100%",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--gov-border)",
                backgroundColor: "var(--gov-surface-secondary)",
                color: "var(--gov-text-secondary)",
                fontSize: "12px",
                fontWeight: 500,
                cursor: "pointer",
                transition: "background-color 0.15s ease",
              }}
            >
              <NavIcon name={isCollapsed ? "chevronRight" : "chevronLeft"} size={16} />
              {!isCollapsed && <span>Collapse Sidebar</span>}
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
