"use client";

import React from "react";
import { AppShell, PageContainer } from "@/components/layout";
import { AccessDenied } from "@/components/auth/AccessDenied";

export default function AccessDeniedPage() {
  return (
    <AppShell>
      <PageContainer maxWidth="lg">
        <AccessDenied
          title="Access Restricted"
          message="You do not possess the required permissions to access this procurement module or administrative view."
        />
      </PageContainer>
    </AppShell>
  );
}
