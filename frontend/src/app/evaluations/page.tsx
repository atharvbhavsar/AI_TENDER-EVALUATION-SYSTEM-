"use client";

import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader, EmptyState, StatusBadge } from "@/components/ui";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

function EvaluationsContent() {
  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="Deterministic Evaluations & Ranking"
          description="Deterministic Open Policy Agent (OPA) rule execution, criterion qualification matrices, and comparative L1/L2 ranking."
          badge={<StatusBadge status="QUALIFIED_RANKED" size="sm" />}
          breadcrumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Evaluations" }]}
        />

        <EmptyState
          icon="⚖️"
          title="Evaluations & Ranking Architecture Ready"
          description="Foundation established. OPA Rego rule results, qualification breakdowns, and ranking views will be connected in Phase 7+."
        />
      </PageContainer>
    </AppShell>
  );
}

export default function EvaluationsPage() {
  return (
    <ProtectedRoute requiredPermission="EVALUATION_READ">
      <EvaluationsContent />
    </ProtectedRoute>
  );
}
