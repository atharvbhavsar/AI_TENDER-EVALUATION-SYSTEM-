"use client";

import { useEffect } from "react";
import { AppShell, PageContainer } from "@/components/layout";
import { ErrorState } from "@/components/ui";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log clean diagnostic info without sensitive params
    if (process.env.NODE_ENV === "development") {
      console.error("Root error boundary triggered:", error);
    }
  }, [error]);

  return (
    <AppShell>
      <PageContainer maxWidth="lg">
        <div style={{ marginTop: "40px" }}>
          <ErrorState
            title="Application Error"
            error="An unexpected issue occurred while rendering this view. Your session and saved data remain secure."
            onRetry={() => reset()}
          />
        </div>
      </PageContainer>
    </AppShell>
  );
}
