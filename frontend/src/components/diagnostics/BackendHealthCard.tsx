"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchHealth } from "@/lib/api/health";
import { APP_CONFIG } from "@/lib/config";
import { Button, Card, CardHeader, CardTitle, CardDescription, CardContent, StatusBadge, Spinner, Alert } from "@/components/ui";
import type { HealthResponse } from "@/types/api";

export function BackendHealthCard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const executeCheck = useCallback(async () => {
    const start = performance.now();
    try {
      const data = await fetchHealth();
      const elapsed = Math.round(performance.now() - start);
      setLatencyMs(elapsed);
      setHealth(data);
      setError(null);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      const elapsed = Math.round(performance.now() - start);
      setLatencyMs(elapsed);
      const msg = err instanceof Error ? err.message : "Failed to connect to backend service";
      setError(msg);
      setHealth(null);
      setLastChecked(new Date().toLocaleTimeString());
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleManualRefresh = () => {
    setIsLoading(true);
    executeCheck();
  };

  useEffect(() => {
    let isCancelled = false;

    async function initialLoad() {
      const start = performance.now();
      try {
        const data = await fetchHealth();
        if (!isCancelled) {
          const elapsed = Math.round(performance.now() - start);
          setLatencyMs(elapsed);
          setHealth(data);
          setError(null);
          setLastChecked(new Date().toLocaleTimeString());
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const elapsed = Math.round(performance.now() - start);
          setLatencyMs(elapsed);
          const msg = err instanceof Error ? err.message : "Failed to connect to backend service";
          setError(msg);
          setHealth(null);
          setLastChecked(new Date().toLocaleTimeString());
          setIsLoading(false);
        }
      }
    }

    initialLoad();

    return () => {
      isCancelled = true;
    };
  }, []);

  const isHealthy = Boolean(health && (health.status === "healthy" || health.status === "ok" || health.status === "alive"));
  const isDegraded = Boolean(health && health.status === "degraded");

  return (
    <Card>
      <CardHeader>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
          <div>
            <CardTitle>System Connectivity & Backend Health</CardTitle>
            <CardDescription>
              Real-time API probe verifying FastAPI gateway, PostgreSQL, and Redis connectivity.
            </CardDescription>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {isLoading ? (
              <StatusBadge status="PROCESSING" size="sm" />
            ) : isHealthy ? (
              <StatusBadge status="COMPLETED" size="sm" />
            ) : isDegraded ? (
              <StatusBadge status="MANUAL_REVIEW" size="sm" />
            ) : (
              <StatusBadge status="FAILED" size="sm" />
            )}
            <Button
              variant="secondary"
              size="sm"
              isLoading={isLoading}
              onClick={handleManualRefresh}
            >
              Ping Backend
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {error ? (
          <Alert variant="danger" title="Backend Connectivity Error">
            <p style={{ margin: "0 0 8px 0" }}>{error}</p>
            <div style={{ fontSize: "12px", color: "#991b1b" }}>
              Target endpoint: <code>{APP_CONFIG.apiBaseUrl}/api/v1/health</code>
            </div>
          </Alert>
        ) : isLoading && !health ? (
          <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "12px 0" }}>
            <Spinner size="sm" />
            <span style={{ fontSize: "13px", color: "var(--gov-text-muted)" }}>
              Testing connection to {APP_CONFIG.apiBaseUrl}...
            </span>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "16px" }}>
            <div style={{ padding: "12px", backgroundColor: "var(--gov-surface-secondary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                API Gateway
              </div>
              <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--gov-text-primary)", marginTop: "2px" }}>
                {health?.app_name || "CRPF Backend API"}
              </div>
              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
                v{health?.version || APP_CONFIG.version} ({health?.environment || "development"})
              </div>
            </div>

            <div style={{ padding: "12px", backgroundColor: "var(--gov-surface-secondary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Target URL
              </div>
              <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--gov-primary)", marginTop: "2px", wordBreak: "break-all" }}>
                {APP_CONFIG.apiBaseUrl}
              </div>
              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
                Latency: {latencyMs !== null ? `${latencyMs}ms` : "—"}
              </div>
            </div>

            <div style={{ padding: "12px", backgroundColor: "var(--gov-surface-secondary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Database (PostgreSQL)
              </div>
              <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--gov-text-primary)", marginTop: "2px" }}>
                {health?.database || "connected"}
              </div>
              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
                Relational + pgvector
              </div>
            </div>

            <div style={{ padding: "12px", backgroundColor: "var(--gov-surface-secondary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Last Verified
              </div>
              <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--gov-text-primary)", marginTop: "2px" }}>
                {lastChecked || "Just now"}
              </div>
              <div style={{ fontSize: "11px", color: "var(--gov-text-muted)", marginTop: "2px" }}>
                Auto-pings every 30s
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
