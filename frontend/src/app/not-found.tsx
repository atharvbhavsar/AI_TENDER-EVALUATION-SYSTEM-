import Link from "next/link";
import { AppShell, PageContainer } from "@/components/layout";
import { EmptyState, Button } from "@/components/ui";

export default function NotFound() {
  return (
    <AppShell>
      <PageContainer maxWidth="md">
        <div style={{ marginTop: "60px" }}>
          <EmptyState
            icon="404"
            title="Page Not Found"
            description="The requested page could not be located on the CRPF Tender Evaluation system. It may have been moved or archived."
            action={
              <Link href="/dashboard" style={{ textDecoration: "none" }}>
                <Button variant="primary" size="md">
                  Return to Dashboard
                </Button>
              </Link>
            }
          />
        </div>
      </PageContainer>
    </AppShell>
  );
}
