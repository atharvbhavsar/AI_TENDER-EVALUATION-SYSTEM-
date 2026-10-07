"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { ErrorState } from "../ui/ErrorState";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // In production, send to centralized telemetry if available; do not log sensitive data
    if (process.env.NODE_ENV === "development") {
      console.error("ErrorBoundary caught an error:", error, errorInfo);
    }
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={{ padding: "32px", width: "100%", maxWidth: "600px", margin: "40px auto" }}>
          <ErrorState
            title="An unexpected interface error occurred"
            error={
              process.env.NODE_ENV === "development"
                ? this.state.error?.message || "Render error"
                : "A component failed to render properly. You may refresh the page or try again."
            }
            onRetry={this.handleReset}
          />
        </div>
      );
    }

    return this.props.children;
  }
}
