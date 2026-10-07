"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { fetchHealth } from "@/lib/api/health";
import { APP_CONFIG } from "@/lib/config";
import { UserMenu } from "./UserMenu";
import { NavIcon } from "./NavIcons";

export interface HeaderProps {
  onMenuToggle?: () => void;
  isMobileOpen?: boolean;
}

export function Header({ onMenuToggle, isMobileOpen = false }: HeaderProps) {
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "disconnected">("checking");

  useEffect(() => {
    let isMounted = true;
    async function checkConnectivity() {
      try {
        const res = await fetchHealth();
        if (isMounted) {
          setBackendStatus(res?.status ? "connected" : "disconnected");
        }
      } catch {
        if (isMounted) {
          setBackendStatus("disconnected");
        }
      }
    }

    checkConnectivity();
    const timer = setInterval(checkConnectivity, 30000);
    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <header
      style={{
        height: "56px",
        backgroundColor: "var(--gov-primary)",
        color: "#ffffff",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 16px",
        borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
        position: "sticky",
        top: 0,
        zIndex: 50,
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Left: Mobile Navigation Drawer Trigger & CRPF Branding */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {onMenuToggle && (
          <button
            type="button"
            onClick={onMenuToggle}
            aria-label={isMobileOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={isMobileOpen}
            style={{
              background: "none",
              border: "none",
              color: "#ffffff",
              cursor: "pointer",
              padding: "6px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <NavIcon name={isMobileOpen ? "close" : "menu"} size={20} />
          </button>
        )}

        <Link
          href="/dashboard"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            color: "#ffffff",
            textDecoration: "none",
          }}
        >
          {/* Government / CRPF Insignia */}
          <div
            style={{
              width: "32px",
              height: "32px",
              backgroundColor: "var(--gov-gold)",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 800,
              fontSize: "13px",
              color: "#0b2545",
              boxShadow: "0 0 0 1px rgba(255,255,255,0.25)",
              flexShrink: 0,
            }}
            aria-hidden="true"
          >
            CRPF
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "14px", fontWeight: 700, letterSpacing: "0.02em", lineHeight: 1.2 }}>
              AI TENDER EVALUATION
            </span>
            <span style={{ fontSize: "10px", color: "#93c5fd", letterSpacing: "0.03em" }}>
              Technical Eligibility & Deterministic Ranking
            </span>
          </div>
        </Link>
      </div>

      {/* Right: Backend Diagnostic Indicator & UserMenu */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {/* Backend Connectivity Indicator */}
        <div
          title={`Backend API Endpoint: ${APP_CONFIG.apiBaseUrl}`}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "3px 8px",
            borderRadius: "4px",
            backgroundColor: "rgba(255, 255, 255, 0.08)",
            fontSize: "11px",
            fontWeight: 500,
          }}
        >
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor:
                backendStatus === "connected"
                  ? "#22c55e"
                  : backendStatus === "disconnected"
                  ? "#ef4444"
                  : "#eab308",
              display: "inline-block",
            }}
            aria-hidden="true"
          />
          <span style={{ color: "#e2e8f0" }}>
            API: {backendStatus === "connected" ? "ONLINE" : backendStatus === "disconnected" ? "OFFLINE" : "CHECKING"}
          </span>
        </div>

        {/* Reusable Authenticated User Menu */}
        <UserMenu />
      </div>
    </header>
  );
}
