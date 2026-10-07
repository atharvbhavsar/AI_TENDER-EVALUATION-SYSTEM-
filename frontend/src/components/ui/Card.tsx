import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Card({ children, className = "", style, ...props }: CardProps) {
  return (
    <div
      style={{
        backgroundColor: "var(--gov-surface)",
        border: "1px solid var(--gov-border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        overflow: "hidden",
        ...style,
      }}
      className={`gov-card ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className = "",
  style,
  ...props
}: CardProps) {
  return (
    <div
      style={{
        padding: "16px 20px",
        borderBottom: "1px solid var(--gov-border)",
        backgroundColor: "var(--gov-surface)",
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        ...style,
      }}
      className={`gov-card-header ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({
  children,
  className = "",
  style,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      style={{
        margin: 0,
        fontSize: "15px",
        fontWeight: 600,
        color: "var(--gov-text-primary)",
        letterSpacing: "-0.01em",
        ...style,
      }}
      className={`gov-card-title ${className}`}
      {...props}
    >
      {children}
    </h3>
  );
}

export function CardDescription({
  children,
  className = "",
  style,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      style={{
        margin: 0,
        fontSize: "13px",
        color: "var(--gov-text-muted)",
        lineHeight: 1.4,
        ...style,
      }}
      className={`gov-card-desc ${className}`}
      {...props}
    >
      {children}
    </p>
  );
}

export function CardContent({
  children,
  className = "",
  style,
  ...props
}: CardProps) {
  return (
    <div
      style={{
        padding: "20px",
        ...style,
      }}
      className={`gov-card-content ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardFooter({
  children,
  className = "",
  style,
  ...props
}: CardProps) {
  return (
    <div
      style={{
        padding: "12px 20px",
        borderTop: "1px solid var(--gov-border)",
        backgroundColor: "var(--gov-surface-secondary)",
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-end",
        gap: "10px",
        ...style,
      }}
      className={`gov-card-footer ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
