"use client";

import React, { useState, useSyncExternalStore } from "react";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export interface AppShellProps {
  children: React.ReactNode;
  showSidebar?: boolean;
}

const SIDEBAR_COLLAPSED_STORAGE_KEY = "crpf_sidebar_collapsed";

const listeners = new Set<() => void>();

function notifyCollapseListeners() {
  listeners.forEach((listener) => listener());
}

function subscribeCollapse(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getCollapseSnapshot(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function getCollapseServerSnapshot(): boolean {
  return false;
}

export function AppShell({ children, showSidebar = true }: AppShellProps) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const isCollapsed = useSyncExternalStore(
    subscribeCollapse,
    getCollapseSnapshot,
    getCollapseServerSnapshot
  );

  const handleToggleCollapse = () => {
    const next = !isCollapsed;
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(next));
    } catch {
      // Storage unavailable
    }
    notifyCollapseListeners();
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "var(--gov-bg)",
      }}
    >
      {/* Skip to main content link for keyboard accessibility */}
      <a
        href="#main-content"
        style={{
          position: "absolute",
          top: "-40px",
          left: "8px",
          backgroundColor: "var(--gov-primary)",
          color: "#ffffff",
          padding: "8px 12px",
          zIndex: 100,
          borderRadius: "4px",
          fontSize: "12px",
          fontWeight: 600,
          transition: "top 0.15s ease",
          textDecoration: "none",
        }}
        onFocus={(e) => {
          (e.currentTarget as HTMLElement).style.top = "8px";
        }}
        onBlur={(e) => {
          (e.currentTarget as HTMLElement).style.top = "-40px";
        }}
      >
        Skip to main content
      </a>

      <Header
        onMenuToggle={showSidebar ? () => setIsMobileOpen((prev) => !prev) : undefined}
        isMobileOpen={isMobileOpen}
      />

      <div style={{ display: "flex", flex: 1, minHeight: "calc(100vh - 56px - 36px)" }}>
        {showSidebar && (
          <Sidebar
            isMobileOpen={isMobileOpen}
            onMobileClose={() => setIsMobileOpen(false)}
            isCollapsed={isCollapsed}
            onToggleCollapse={handleToggleCollapse}
          />
        )}

        <main
          id="main-content"
          tabIndex={-1}
          style={{
            flex: 1,
            minWidth: 0,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {children}
        </main>
      </div>

      {/* Institutional CRPF System Footer / Status Area */}
      <footer
        style={{
          height: "36px",
          backgroundColor: "#ffffff",
          borderTop: "1px solid var(--gov-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 16px",
          fontSize: "11px",
          color: "var(--gov-text-muted)",
          zIndex: 30,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontWeight: 600, color: "var(--gov-text-secondary)" }}>
            Central Reserve Police Force
          </span>
          <span>•</span>
          <span>Directorate General of Procurement</span>
          <span>•</span>
          <span>Ministry of Home Affairs</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span>Deterministic OPA Rego Engine: Active</span>
          <span>•</span>
          <span style={{ color: "#166534", fontWeight: 600 }}>● System Operational</span>
        </div>
      </footer>
    </div>
  );
}
