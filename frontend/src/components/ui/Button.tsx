import React from "react";
import { Spinner } from "./Spinner";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = "primary",
      size = "md",
      isLoading = false,
      disabled = false,
      leftIcon,
      rightIcon,
      className = "",
      style,
      type = "button",
      ...props
    },
    ref
  ) => {
    // Style configurations based on variant
    const variantStyles: Record<string, React.CSSProperties> = {
      primary: {
        backgroundColor: "var(--gov-primary)",
        color: "#ffffff",
        border: "1px solid var(--gov-primary)",
      },
      secondary: {
        backgroundColor: "var(--gov-surface-secondary)",
        color: "var(--gov-text-primary)",
        border: "1px solid var(--gov-border-strong)",
      },
      outline: {
        backgroundColor: "transparent",
        color: "var(--gov-primary)",
        border: "1px solid var(--gov-border-strong)",
      },
      danger: {
        backgroundColor: "#dc2626",
        color: "#ffffff",
        border: "1px solid #b91c1c",
      },
      ghost: {
        backgroundColor: "transparent",
        color: "var(--gov-text-secondary)",
        border: "1px solid transparent",
      },
    };

    // Size configurations
    const sizeStyles: Record<string, React.CSSProperties> = {
      sm: {
        padding: "6px 12px",
        fontSize: "12px",
        borderRadius: "var(--radius-sm)",
        height: "30px",
      },
      md: {
        padding: "8px 16px",
        fontSize: "13px",
        borderRadius: "var(--radius-md)",
        height: "36px",
      },
      lg: {
        padding: "10px 20px",
        fontSize: "14px",
        borderRadius: "var(--radius-md)",
        height: "42px",
      },
    };

    const baseStyle: React.CSSProperties = {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      fontWeight: 500,
      cursor: disabled || isLoading ? "not-allowed" : "pointer",
      opacity: disabled ? 0.6 : 1,
      transition: "background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease",
      gap: "8px",
      userSelect: "none",
      textDecoration: "none",
      ...variantStyles[variant],
      ...sizeStyles[size],
      ...style,
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isLoading}
        aria-busy={isLoading}
        style={baseStyle}
        className={`gov-button ${className}`}
        {...props}
      >
        {isLoading ? (
          <>
            <Spinner size="sm" light={variant === "primary" || variant === "danger"} />
            <span>Processing...</span>
          </>
        ) : (
          <>
            {leftIcon && <span style={{ display: "inline-flex" }}>{leftIcon}</span>}
            {children}
            {rightIcon && <span style={{ display: "inline-flex" }}>{rightIcon}</span>}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = "Button";
