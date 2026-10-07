"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell, PageContainer } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, Input, Button, Alert, Spinner } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, isAuthenticated, isLoading: authLoading, currentUser } = useAuth();

  const returnUrl = searchParams.get("returnUrl") || "/dashboard";
  const sessionExpired = searchParams.get("session_expired") === "true";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  // If already authenticated, redirect to destination
  useEffect(() => {
    if (!authLoading && isAuthenticated && currentUser) {
      if (returnUrl === "/dashboard" && currentUser.roles.includes("BIDDER") && !currentUser.roles.includes("PROCUREMENT_OFFICER")) {
        router.push("/bidder/dashboard");
      } else {
        router.push(returnUrl);
      }
    }
  }, [authLoading, isAuthenticated, currentUser, router, returnUrl]);

  const validateForm = (): boolean => {
    let isValid = true;
    setEmailError(null);
    setPasswordError(null);
    setServerError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setEmailError("Email address is required.");
      isValid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setEmailError("Please enter a valid email address.");
      isValid = false;
    }

    if (!password) {
      setPasswordError("Password is required.");
      isValid = false;
    } else if (password.length < 6) {
      setPasswordError("Password must be at least 6 characters.");
      isValid = false;
    }

    return isValid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setServerError(null);

    try {
      await login({ email: email.trim(), password });
      router.push(returnUrl);
    } catch (err: unknown) {
      if (err && typeof err === "object" && "info" in err) {
        const errorInfo = (err as { info: { statusCode?: number; message?: string } }).info;
        if (errorInfo.statusCode === 401) {
          setServerError("Invalid email address or password. Please verify your credentials.");
        } else if (errorInfo.statusCode === 422) {
          setServerError("Validation error. Please verify the credentials provided.");
        } else if (errorInfo.statusCode === 403) {
          setServerError("Your account is deactivated or unauthorized for sign in.");
        } else {
          setServerError(errorInfo.message || "Failed to authenticate with backend server.");
        }
      } else {
        const msg = err instanceof Error ? err.message : "Authentication failed.";
        setServerError(msg);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const fillCredentials = (userEmail: string, pass: string) => {
    setEmail(userEmail);
    setPassword(pass);
    setEmailError(null);
    setPasswordError(null);
    setServerError(null);
  };

  return (
    <div style={{ maxWidth: "460px", margin: "40px auto", width: "100%" }}>
      <Card>
        <CardHeader>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
            <span
              style={{
                backgroundColor: "var(--gov-gold)",
                color: "#0b2545",
                fontWeight: 700,
                padding: "2px 6px",
                borderRadius: "4px",
                fontSize: "11px",
              }}
            >
              AUTHENTICATION
            </span>
            <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
              Central Reserve Police Force
            </span>
          </div>
          <CardTitle>Sign In to Evaluation Platform</CardTitle>
          <CardDescription>
            Authenticate with your authorized government credentials to access procurement evaluation modules.
          </CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit} noValidate>
          <CardContent>
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {sessionExpired && (
                <Alert variant="warning" title="Session Expired">
                  Your previous authenticated session has expired. Please sign in again to continue.
                </Alert>
              )}

              {serverError && (
                <Alert variant="danger" title="Authentication Failed">
                  {serverError}
                </Alert>
              )}

              <Input
                label="Officer Email Address"
                type="email"
                placeholder="officer@crpf.gov.in"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (emailError) setEmailError(null);
                }}
                error={emailError || undefined}
                required
                autoComplete="email"
              />

              <Input
                label="Account Password"
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (passwordError) setPasswordError(null);
                }}
                error={passwordError || undefined}
                required
                autoComplete="current-password"
              />

              {/* Development & Reviewer Pre-seeded Accounts */}
              <div
                style={{
                  padding: "12px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "var(--gov-surface-secondary)",
                  border: "1px solid var(--gov-border)",
                  fontSize: "12px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                <div style={{ fontWeight: 600, color: "var(--gov-text-secondary)" }}>
                  Verified Test Roles (Click to autofill):
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  <button
                    type="button"
                    onClick={() => fillCredentials("officer@crpf.gov.in", "OfficerPassword123!")}
                    style={{
                      padding: "4px 8px",
                      fontSize: "11px",
                      borderRadius: "4px",
                      border: "1px solid var(--gov-border-strong)",
                      backgroundColor: "#ffffff",
                      cursor: "pointer",
                      fontWeight: 500,
                    }}
                  >
                    Procurement Officer
                  </button>
                  <button
                    type="button"
                    onClick={() => fillCredentials("admin@crpf.gov.in", "AdminPassword123!")}
                    style={{
                      padding: "4px 8px",
                      fontSize: "11px",
                      borderRadius: "4px",
                      border: "1px solid var(--gov-border-strong)",
                      backgroundColor: "#ffffff",
                      cursor: "pointer",
                      fontWeight: 500,
                    }}
                  >
                    Administrator
                  </button>
                  <button
                    type="button"
                    onClick={() => fillCredentials("reviewer@crpf.gov.in", "ReviewerPassword123!")}
                    style={{
                      padding: "4px 8px",
                      fontSize: "11px",
                      borderRadius: "4px",
                      border: "1px solid var(--gov-border-strong)",
                      backgroundColor: "#ffffff",
                      cursor: "pointer",
                      fontWeight: 500,
                    }}
                  >
                    Technical Reviewer
                  </button>
                </div>
              </div>
            </div>
          </CardContent>

          <CardFooter>
            <div style={{ display: "flex", flexDirection: "column", gap: "14px", width: "100%" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
                <Link href="/dashboard" style={{ fontSize: "12px", color: "var(--gov-text-muted)", textDecoration: "none" }}>
                  ← View System Overview
                </Link>
                <Button type="submit" variant="primary" size="md" isLoading={isSubmitting}>
                  Sign In
                </Button>
              </div>

              <div
                style={{
                  borderTop: "1px solid var(--gov-border)",
                  paddingTop: "12px",
                  textAlign: "center",
                  fontSize: "12px",
                  color: "var(--gov-text-muted)",
                }}
              >
                Prospective Bidder / Vendor?{" "}
                <Link
                  href={returnUrl && returnUrl !== "/dashboard" ? `/register?returnUrl=${encodeURIComponent(returnUrl)}` : "/register"}
                  style={{ color: "var(--gov-primary)", fontWeight: 700, textDecoration: "underline" }}
                >
                  Register Company Account
                </Link>
              </div>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <AppShell showSidebar={false}>
      <PageContainer maxWidth="lg">
        <Suspense
          fallback={
            <div style={{ display: "flex", justifyContent: "center", padding: "60px" }}>
              <Spinner size="lg" />
            </div>
          }
        >
          <LoginForm />
        </Suspense>
      </PageContainer>
    </AppShell>
  );
}
