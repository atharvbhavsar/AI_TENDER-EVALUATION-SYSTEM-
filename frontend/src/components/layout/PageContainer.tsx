import React from "react";

export interface PageContainerProps {
  children: React.ReactNode;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl" | "full";
  className?: string;
  style?: React.CSSProperties;
}

export function PageContainer({
  children,
  maxWidth = "xl",
  className = "",
  style,
}: PageContainerProps) {
  const maxWidthMap = {
    sm: "640px",
    md: "768px",
    lg: "1024px",
    xl: "1280px",
    "2xl": "1536px",
    full: "100%",
  };

  return (
    <div
      style={{
        width: "100%",
        maxWidth: maxWidthMap[maxWidth],
        margin: "0 auto",
        padding: "24px 24px 48px 24px",
        ...style,
      }}
      className={`gov-page-container ${className}`}
    >
      {children}
    </div>
  );
}
