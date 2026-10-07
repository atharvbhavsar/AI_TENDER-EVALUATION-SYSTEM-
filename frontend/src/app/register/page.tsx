"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell, PageContainer } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, Input, Button, Alert, Spinner } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { register, isAuthenticated, isLoading: authLoading, currentUser } = useAuth();

  const returnUrl = searchParams.get("returnUrl") || "/bidder/dashboard";

  const [companyName, setCompanyName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [formErrors, setFormErrors] = useState<{ [key: string]: string }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  // If already authenticated, redirect
  useEffect(() => {
    if (!authLoading && isAuthenticated && currentUser) {
      router.push(returnUrl);
    }
  }, [authLoading, isAuthenticated, currentUser, router, returnUrl]);

  const validate = (): boolean => {
    const errors: { [key: string]: string } = {};
    setServerError(null);

    if (!companyName.trim()) {
      errors.companyName = "Corporate legal entity name is required.";
    }
    if (!fullName.trim()) {
      errors.fullName = "Representative full name is required.";
    }

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      errors.email = "Corporate email address is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      errors.email = "Please enter a valid corporate email address.";
    }

    if (!password) {
      errors["password"] = "Password is required.";
    } else if (password.length < 8) {
      errors["password"] = "Password must be at least 8 characters.";
    }

    if (password !== confirmPassword) {
      errors["confirmPassword"] = "Passwords do not match.";
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    setServerError(null);
    try {
      await register({
        company_name: companyName.trim(),
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim() || undefined,
        password,
      });
      router.push(returnUrl);
    } catch (err: unknown) {
      const errObj = err as { info?: { statusCode?: number; message?: string }; message?: string };
      if (errObj?.info?.statusCode === 409) {
        setServerError("An account with this corporate email address already exists. Please sign in instead.");
      } else {
        setServerError(errObj?.info?.message || errObj?.message || "Registration failed. Please check details and try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: "560px", margin: "40px auto" }}>
      <Card>
        <CardHeader>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
            <span style={{ fontSize: "28px" }} aria-hidden="true">🏢</span>
            <div>
              <CardTitle style={{ fontSize: "20px" }}>Bidder Registration Portal</CardTitle>
              <CardDescription>
                Register your business entity to participate in official CRPF tenders.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <form onSubmit={handleSubmit} noValidate>
          <CardContent style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {serverError && (
              <Alert variant="danger" title="Registration Error">
                {serverError}
              </Alert>
            )}

            <div>
              <label htmlFor="companyName" style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                Company / Organization Legal Name *
              </label>
              <Input
                id="companyName"
                type="text"
                required
                placeholder="e.g. Apex Defense & Tactical Systems Pvt Ltd"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                error={formErrors.companyName}
              />
            </div>

            <div>
              <label htmlFor="fullName" style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                Authorized Contact Representative *
              </label>
              <Input
                id="fullName"
                type="text"
                required
                placeholder="e.g. Rajesh Kumar Sharma"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                error={formErrors.fullName}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div>
                <label htmlFor="email" style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                  Corporate Email *
                </label>
                <Input
                  id="email"
                  type="email"
                  required
                  placeholder="bids@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  error={formErrors.email}
                />
              </div>

              <div>
                <label htmlFor="phone" style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                  Contact Phone Number
                </label>
                <Input
                  id="phone"
                  type="tel"
                  placeholder="+91 9876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div>
                <label htmlFor="password" style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                  Password *
                </label>
                <Input
                  id="password"
                  type="password"
                  required
                  placeholder="At least 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  error={formErrors.password}
                />
              </div>

              <div>
                <label htmlFor="confirmPassword" style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                  Confirm Password *
                </label>
                <Input
                  id="confirmPassword"
                  type="password"
                  required
                  placeholder="Re-enter password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  error={formErrors.confirmPassword}
                />
              </div>
            </div>

            <div
              style={{
                fontSize: "11px",
                color: "var(--gov-text-muted)",
                backgroundColor: "var(--gov-surface-secondary)",
                padding: "8px 12px",
                borderRadius: "var(--radius-md)",
                lineHeight: 1.4,
              }}
            >
              🔒 By registering, you agree to statutory procurement regulations pursuant to the General Financial Rules (GFR), 2017.
            </div>
          </CardContent>

          <CardFooter>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", width: "100%" }}>
              <Button type="submit" variant="primary" size="md" isLoading={isSubmitting}>
                Register & Enter Bidder Portal →
              </Button>

              <div style={{ textAlign: "center", fontSize: "12px", color: "var(--gov-text-muted)" }}>
                Already registered?{" "}
                <Link
                  href={returnUrl && returnUrl !== "/bidder/dashboard" ? `/login?returnUrl=${encodeURIComponent(returnUrl)}` : "/login"}
                  style={{ color: "var(--gov-primary)", fontWeight: 700, textDecoration: "underline" }}
                >
                  Sign In to Bidder Account
                </Link>
              </div>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

export default function RegisterPage() {
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
          <RegisterForm />
        </Suspense>
      </PageContainer>
    </AppShell>
  );
}
