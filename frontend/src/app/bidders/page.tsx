"use client";

import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader, EmptyState, StatusBadge } from "@/components/ui";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

function BiddersContent() {
  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="Bidder Submissions & Ingestion"
          description="View submitted bidder proposals, document intake integrity, and automated OCR processing."
          badge={<StatusBadge status="READY" size="sm" />}
          breadcrumbs={[{ label: "Dashboard", href: "/dashboard" }, { label: "Bidders" }]}
        />

        <EmptyState
          icon="🏢"
          title="Bidder Module Architecture Ready"
          description="Foundation established. Multi-bidder document ingestion and OCR pipeline controls will be implemented in subsequent phases."
        />
      </PageContainer>
    </AppShell>
  );
}

export default function BiddersPage() {
  return (
    <ProtectedRoute requiredPermission="BIDDER_READ">
      <BiddersContent />
    </ProtectedRoute>
  );
}
