import React, { useId } from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftAddon?: React.ReactNode;
  rightAddon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      hint,
      id,
      className = "",
      leftAddon,
      rightAddon,
      disabled,
      required,
      style,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const inputId = id || generatedId;
    const errorId = `${inputId}-error`;
    const hintId = `${inputId}-hint`;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", width: "100%" }}>
        {label && (
          <label
            htmlFor={inputId}
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color: "var(--gov-text-secondary)",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <span>{label}</span>
            {required && (
              <span aria-hidden="true" style={{ color: "#dc2626" }}>
                *
              </span>
            )}
          </label>
        )}

        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            width: "100%",
          }}
        >
          {leftAddon && (
            <span
              style={{
                position: "absolute",
                left: "10px",
                display: "inline-flex",
                alignItems: "center",
                color: "var(--gov-text-muted)",
                pointerEvents: "none",
              }}
            >
              {leftAddon}
            </span>
          )}

          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            required={required}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : hint ? hintId : undefined}
            style={{
              width: "100%",
              height: "36px",
              padding: leftAddon
                ? rightAddon
                  ? "8px 36px"
                  : "8px 12px 8px 36px"
                : rightAddon
                ? "8px 36px 8px 12px"
                : "8px 12px",
              fontSize: "13px",
              backgroundColor: disabled ? "var(--gov-surface-secondary)" : "var(--gov-surface)",
              color: "var(--gov-text-primary)",
              border: `1px solid ${error ? "#ef4444" : "var(--gov-border-strong)"}`,
              borderRadius: "var(--radius-md)",
              outline: "none",
              transition: "border-color 0.15s ease, box-shadow 0.15s ease",
              boxShadow: "var(--shadow-sm)",
              ...style,
            }}
            className={`gov-input ${className}`}
            {...props}
          />

          {rightAddon && (
            <span
              style={{
                position: "absolute",
                right: "10px",
                display: "inline-flex",
                alignItems: "center",
                color: "var(--gov-text-muted)",
              }}
            >
              {rightAddon}
            </span>
          )}
        </div>

        {error && (
          <span
            id={errorId}
            role="alert"
            style={{
              fontSize: "12px",
              color: "#dc2626",
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <span>⚠</span>
            <span>{error}</span>
          </span>
        )}

        {!error && hint && (
          <span
            id={hintId}
            style={{
              fontSize: "11px",
              color: "var(--gov-text-muted)",
            }}
          >
            {hint}
          </span>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
