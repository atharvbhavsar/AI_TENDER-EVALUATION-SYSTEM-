"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

export function UserMenu() {
  const { currentUser, isAuthenticated, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Close dropdown on Escape key or outside click
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && isOpen) {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    }

    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  if (!isAuthenticated || !currentUser) {
    return (
      <Link
        href="/login"
        style={{
          color: "#ffffff",
          backgroundColor: "rgba(255, 255, 255, 0.12)",
          padding: "6px 14px",
          borderRadius: "4px",
          fontSize: "12px",
          fontWeight: 600,
          textDecoration: "none",
          border: "1px solid rgba(255, 255, 255, 0.2)",
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
        }}
      >
        <span>Sign In</span>
      </Link>
    );
  }

  const primaryRole = currentUser.roles?.[0] || "OFFICER";
  const initials = currentUser.full_name
    ? currentUser.full_name
        .split(" ")
        .map((n) => n[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "CR";

  return (
    <div ref={menuRef} style={{ position: "relative" }}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        aria-label={`User menu for ${currentUser.full_name}`}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          backgroundColor: isOpen ? "rgba(255, 255, 255, 0.18)" : "rgba(255, 255, 255, 0.12)",
          border: "1px solid rgba(255, 255, 255, 0.2)",
          borderRadius: "var(--radius-md)",
          padding: "4px 10px",
          color: "#ffffff",
          cursor: "pointer",
          fontSize: "13px",
          fontWeight: 600,
          transition: "background-color 0.15s ease",
        }}
      >
        <span
          style={{
            width: "24px",
            height: "24px",
            borderRadius: "50%",
            backgroundColor: "var(--gov-gold)",
            color: "#0b2545",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "11px",
            fontWeight: 800,
          }}
          aria-hidden="true"
        >
          {initials}
        </span>

        <span style={{ maxWidth: "160px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {currentUser.full_name}
        </span>

        <span
          style={{
            backgroundColor: "rgba(255, 255, 255, 0.2)",
            padding: "1px 6px",
            borderRadius: "3px",
            fontSize: "10px",
            fontWeight: 700,
            letterSpacing: "0.02em",
          }}
        >
          {primaryRole.replace("_", " ")}
        </span>

        <span style={{ fontSize: "10px", opacity: 0.8 }} aria-hidden="true">
          {isOpen ? "▲" : "▼"}
        </span>
      </button>

      {isOpen && (
        <div
          role="menu"
          aria-label="User actions"
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 6px)",
            width: "250px",
            backgroundColor: "#ffffff",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-lg)",
            border: "1px solid var(--gov-border)",
            zIndex: 70,
            color: "var(--gov-text-primary)",
            padding: "8px 0",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* User Details */}
          <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--gov-border)" }}>
            <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--gov-text-primary)" }}>
              {currentUser.full_name}
            </div>
            <div style={{ fontSize: "12px", color: "var(--gov-text-muted)", marginTop: "1px" }}>
              {currentUser.email}
            </div>

            <div style={{ marginTop: "8px", display: "flex", flexWrap: "wrap", gap: "4px" }}>
              {currentUser.roles.map((r) => (
                <span
                  key={r}
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: "3px",
                    backgroundColor: "var(--status-info-bg)",
                    color: "var(--status-info-text)",
                    border: "1px solid var(--status-info-border)",
                  }}
                >
                  {r}
                </span>
              ))}
            </div>
          </div>

          {/* Authorization Summary */}
          <div style={{ padding: "8px 16px", fontSize: "11px", color: "var(--gov-text-muted)" }}>
            <span>Account Clearance: </span>
            <strong style={{ color: "var(--gov-text-secondary)" }}>
              {currentUser.permissions.length} permissions active
            </strong>
          </div>

          {/* Logout Action */}
          <div style={{ borderTop: "1px solid var(--gov-border)", padding: "4px 8px" }}>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setIsOpen(false);
                logout();
              }}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "8px 10px",
                backgroundColor: "transparent",
                border: "none",
                color: "#dc2626",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                borderRadius: "var(--radius-sm)",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span aria-hidden="true">🚪</span>
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
