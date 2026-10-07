import React from "react";

export interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
  light?: boolean;
}

export function Spinner({
  size = "md",
  className = "",
  label = "Loading...",
  light = false,
}: SpinnerProps) {
  const sizePixels = size === "sm" ? 16 : size === "lg" ? 32 : 22;
  const strokeColor = light ? "#ffffff" : "var(--gov-primary)";

  return (
    <span
      role="status"
      aria-label={label}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      className={className}
    >
      <svg
        width={sizePixels}
        height={sizePixels}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="animate-gov-spin"
      >
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke={light ? "rgba(255, 255, 255, 0.25)" : "rgba(11, 37, 69, 0.15)"}
          strokeWidth="3"
        />
        <path
          d="M12 2a10 10 0 0 1 10 10"
          stroke={strokeColor}
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0, 0, 0, 0)" }}>
        {label}
      </span>
    </span>
  );
}
