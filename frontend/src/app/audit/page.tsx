"use client";

import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader, EmptyState, StatusBadge } from "@/components/ui";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

function AuditContent() {
  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="Regulatory Audit Trail & Provenance"
          description="Tamper-evident logs of all automated and human decisions, system state changes, and evidence verification signatures."
          badge={<StatusBadge status="RESOLVED" size="sm" />}
          breadcrumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Audit" }]}
        />

        <EmptyState
          icon="🛡️"
          title="Audit Trail Architecture Ready"
          description="Foundation established. Append-only regulatory audit log viewer and cryptographic verification will be connected in Phase 15."
        />
      </PageContainer>
    </AppShell>
  );
}

export default function AuditPage() {
  return (
    <ProtectedRoute requiredPermission="USER_MANAGE">
      <AuditContent />
    </ProtectedRoute>
  );
}
