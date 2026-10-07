"use client";

import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader, EmptyState, StatusBadge } from "@/components/ui";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

function ReviewsContent() {
  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="Human Officer Review Workflow"
          description="Resolve ambiguous citations, unreadable documents, conflicting evidence, and record authoritative sign-off decisions."
          badge={<StatusBadge status="MANUAL_REVIEW" size="sm" />}
          breadcrumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Reviews" }]}
        />

        <EmptyState
          icon="🔍"
          title="Human Review Queue Architecture Ready"
          description="Foundation established. Exception queues, side-by-side evidence inspection, and decision logging will be integrated in Phase 14."
        />
      </PageContainer>
    </AppShell>
  );
}

export default function ReviewsPage() {
  return (
    <ProtectedRoute requiredPermissions={["REVIEW_CREATE", "REVIEW_APPROVE"]}>
      <ReviewsContent />
    </ProtectedRoute>
  );
}
