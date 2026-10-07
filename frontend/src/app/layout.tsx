import type { Metadata } from "next";
import "./globals.css";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { AuthProvider } from "@/context/AuthContext";

export const metadata: Metadata = {
  title: "CRPF AI Tender Evaluation & Ranking Platform",
  description:
    "Production-grade government technical eligibility evaluation, deterministic OPA rules, and multi-bidder comparative ranking system.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <ErrorBoundary>
          <AuthProvider>{children}</AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
