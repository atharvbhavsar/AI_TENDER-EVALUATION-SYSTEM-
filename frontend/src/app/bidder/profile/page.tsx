"use client";

import React, { useState, useEffect } from "react";
import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";
import { getBidderProfile, updateBidderProfile, type BidderProfile } from "@/lib/api/bidder";

function ProfileContent() {
  const { refreshUser } = useAuth();
  const [profile, setProfile] = useState<BidderProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form State
  const [companyName, setCompanyName] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");

  useEffect(() => {
    let isMounted = true;
    getBidderProfile()
      .then((data) => {
        if (isMounted) {
          setProfile(data);
          setCompanyName(data.company_name || "");
          setFullName(data.full_name || "");
          setPhone(data.phone || "");
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError((err as Error).message || "Failed to load corporate profile.");
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const updated = await updateBidderProfile({
        company_name: companyName.trim(),
        full_name: fullName.trim(),
        phone: phone.trim() || undefined,
      });
      setProfile(updated);
      await refreshUser();
      setSuccessMsg("Corporate profile updated successfully.");
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: unknown) {
      setError((err as Error).message || "Failed to save profile changes.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    if (profile) {
      setCompanyName(profile.company_name || "");
      setFullName(profile.full_name || "");
      setPhone(profile.phone || "");
      setError(null);
    }
  };

  return (
    <AppShell>
      <PageContainer maxWidth="lg">
        <PageHeader
          title="Corporate Bidder Profile"
          description="Manage registered organization details, authorized contact persons, and statutory contact coordinates."
          breadcrumbs={[
            { label: "Bidder Portal", href: "/bidder/dashboard" },
            { label: "Corporate Profile" },
          ]}
        />

        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "20px" }}>
            <Skeleton width="100%" height="200px" />
            <Skeleton width="100%" height="250px" />
          </div>
        ) : error && !profile ? (
          <div style={{ marginTop: "20px" }}>
            <ErrorState
              title="Failed to Load Profile"
              error={error}
              onRetry={() => {
                setIsLoading(true);
                setError(null);
                getBidderProfile()
                  .then((d) => {
                    setProfile(d);
                    setCompanyName(d.company_name || "");
                    setFullName(d.full_name || "");
                    setPhone(d.phone || "");
                  })
                  .catch((e) => setError((e as Error).message))
                  .finally(() => setIsLoading(false));
              }}
            />
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {successMsg && (
              <Alert variant="success" title="Profile Saved">
                {successMsg}
              </Alert>
            )}

            {error && (
              <Alert variant="danger" title="Update Error">
                {error}
              </Alert>
            )}

            {/* Profile Overview Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-text-muted)", textTransform: "uppercase" }}>
                  Account Status
                </div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#166534", marginTop: "4px" }}>
                  ✓ Active Verified Vendor
                </div>
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-text-muted)", textTransform: "uppercase" }}>
                  Active Applications
                </div>
                <div style={{ fontSize: "20px", fontWeight: 800, color: "var(--gov-primary)", marginTop: "2px" }}>
                  {profile?.active_applications_count ?? 0}
                </div>
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--gov-border)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-text-muted)", textTransform: "uppercase" }}>
                  Registration Timestamp
                </div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--gov-text-secondary)", marginTop: "4px" }}>
                  {profile?.created_at
                    ? new Date(profile.created_at).toLocaleDateString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })
                    : "—"}
                </div>
              </div>
            </div>

            {/* Editable Profile Form */}
            <Card>
              <CardHeader>
                <CardTitle style={{ fontSize: "16px" }}>Organization & Representative Details</CardTitle>
                <CardDescription>
                  Modify the legal name of your entity and authorized communication representatives.
                </CardDescription>
              </CardHeader>

              <form onSubmit={handleSave}>
                <CardContent style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                      Corporate Legal Entity Name *
                    </label>
                    <Input
                      type="text"
                      required
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="e.g. Acme Defense Pvt Ltd"
                    />
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                      Authorized Contact Representative *
                    </label>
                    <Input
                      type="text"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="e.g. Rajesh Kumar"
                    />
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                        Corporate Email (Read-Only)
                      </label>
                      <Input
                        type="email"
                        disabled
                        value={profile?.email || ""}
                        style={{ backgroundColor: "var(--gov-surface-secondary)", cursor: "not-allowed" }}
                      />
                      <span style={{ fontSize: "11px", color: "var(--gov-text-muted)" }}>
                        Primary identifier bound to authentication token.
                      </span>
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>
                        Contact Phone Number
                      </label>
                      <Input
                        type="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="+91 9876543210"
                      />
                    </div>
                  </div>
                </CardContent>

                <CardFooter>
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", width: "100%" }}>
                    <Button type="button" variant="outline" size="sm" onClick={handleReset} disabled={isSaving}>
                      Reset Form
                    </Button>
                    <Button type="submit" variant="primary" size="sm" isLoading={isSaving}>
                      Save Changes
                    </Button>
                  </div>
                </CardFooter>
              </form>
            </Card>
          </div>
        )}
      </PageContainer>
    </AppShell>
  );
}

export default function BidderProfilePage() {
  return (
    <ProtectedRoute requiredPermission="BIDDER_READ">
      <ProfileContent />
    </ProtectedRoute>
  );
}
