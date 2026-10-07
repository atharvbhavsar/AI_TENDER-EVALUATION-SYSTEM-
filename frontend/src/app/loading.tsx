import { AppShell, PageContainer } from "@/components/layout";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";

export default function Loading() {
  return (
    <AppShell>
      <PageContainer maxWidth="xl">
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "24px" }}>
          <Spinner size="md" />
          <span style={{ fontSize: "14px", color: "var(--gov-text-muted)" }}>
            Loading procurement data...
          </span>
        </div>
        <TableSkeleton rows={6} columns={5} />
      </PageContainer>
    </AppShell>
  );
}
