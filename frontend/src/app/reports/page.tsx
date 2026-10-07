"use client";

import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader, EmptyState, StatusBadge } from "@/components/ui";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

function ReportsContent() {
  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="Comparative Reports & PDF Export"
          description="Generate regulatory audit-ready comparative evaluation summaries, L1/L2 award justification, and bidder scorecards."
          badge={<StatusBadge status="COMPLETED" size="sm" />}
          breadcrumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Reports" }]}
        />

        <EmptyState
          icon="📊"
          title="Reporting Engine Architecture Ready"
          description="Foundation established. PDF report generation and download streams will be wired to backend /reports endpoints in Phase 16."
        />
      </PageContainer>
    </AppShell>
  );
}

export default function ReportsPage() {
  return (
    <ProtectedRoute requiredPermission="REPORT_READ">
      <ReportsContent />
    </ProtectedRoute>
  );
}
