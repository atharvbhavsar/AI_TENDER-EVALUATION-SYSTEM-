import React from "react";

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({
  width = "100%",
  height = "20px",
  borderRadius = "var(--radius-sm)",
  className = "",
  style,
}: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: "var(--gov-border)",
        ...style,
      }}
      className={`gov-skeleton animate-gov-pulse ${className}`}
    />
  );
}

export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: "10px" }}>
      <Skeleton height="36px" width="100%" />
      {Array.from({ length: rows }).map((_, rIdx) => (
        <div key={rIdx} style={{ display: "flex", gap: "12px", width: "100%" }}>
          {Array.from({ length: columns }).map((__, cIdx) => (
            <Skeleton key={cIdx} height="28px" style={{ flex: 1 }} />
          ))}
        </div>
      ))}
    </div>
  );
}
