import Link from "next/link";
import { AppShell, PageContainer } from "@/components/layout";
import { PageHeader, Card, CardHeader, CardTitle, CardDescription, CardContent, StatusBadge, Button } from "@/components/ui";
import { BackendHealthCard } from "@/components/diagnostics/BackendHealthCard";

export default function HomePage() {
  const modules = [
    {
      title: "Tender Management",
      desc: "Multi-version tender authoring, corrigenda, and criteria extraction.",
      href: "/tenders",
      status: "READY" as const,
      phase: "Phase 2",
    },
    {
      title: "Bidder Submissions",
      desc: "Multi-bidder submission management, PDF document ingestion, and OCR.",
      href: "/bidders",
      status: "READY" as const,
      phase: "Phase 3-6",
    },
    {
      title: "Evaluations & Ranking",
      desc: "Deterministic OPA rules, qualification matrix, and L1/L2 ranking.",
      href: "/evaluations",
      status: "READY" as const,
      phase: "Phase 7-13, 21",
    },
    {
      title: "Human Review",
      desc: "Exception resolution, ambiguous evidence handling, and officer sign-off.",
      href: "/reviews",
      status: "READY" as const,
      phase: "Phase 14",
    },
    {
      title: "Comparative Reports",
      desc: "High-integrity comparative evaluation and ranking PDF generation.",
      href: "/reports",
      status: "READY" as const,
      phase: "Phase 16",
    },
    {
      title: "Audit Trail",
      desc: "Cryptographic SHA-256 evidence provenance and regulatory audit log.",
      href: "/audit",
      status: "READY" as const,
      phase: "Phase 15",
    },
  ];

  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <PageHeader
          title="CRPF AI Tender Evaluation & Ranking Platform"
          description="Government-grade procurement platform featuring deterministic OPA rule evaluation, multi-bidder comparative analysis, and automated audit trails."
          badge={<StatusBadge status="PUBLISHED" size="sm" />}
          actions={
            <Link href="/login" style={{ textDecoration: "none" }}>
              <Button variant="primary" size="md">
                Sign In to Console
              </Button>
            </Link>
          }
        />

        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Diagnostic Backend Health Check */}
          <BackendHealthCard />

          {/* Core Modules Overview */}
          <div>
            <h2
              style={{
                fontSize: "16px",
                fontWeight: 600,
                color: "var(--gov-text-primary)",
                margin: "0 0 12px 0",
              }}
            >
              System Procurement Modules
            </h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                gap: "16px",
              }}
            >
              {modules.map((m) => (
                <Card key={m.title}>
                  <CardHeader>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--gov-gold)" }}>
                        {m.phase}
                      </span>
                      <StatusBadge status={m.status} size="sm" />
                    </div>
                    <CardTitle style={{ marginTop: "6px" }}>{m.title}</CardTitle>
                    <CardDescription>{m.desc}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Link href={m.href} style={{ textDecoration: "none" }}>
                      <Button variant="secondary" size="sm" style={{ width: "100%" }}>
                        Access Module →
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </PageContainer>
    </AppShell>
  );
}
