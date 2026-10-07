import React, { useId } from "react";

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options?: SelectOption[];
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      error,
      hint,
      id,
      options,
      children,
      className = "",
      disabled,
      required,
      style,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const selectId = id || generatedId;
    const errorId = `${selectId}-error`;
    const hintId = `${selectId}-hint`;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", width: "100%" }}>
        {label && (
          <label
            htmlFor={selectId}
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

        <select
          ref={ref}
          id={selectId}
          disabled={disabled}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : hint ? hintId : undefined}
          style={{
            width: "100%",
            height: "36px",
            padding: "6px 12px",
            fontSize: "13px",
            backgroundColor: disabled ? "var(--gov-surface-secondary)" : "var(--gov-surface)",
            color: "var(--gov-text-primary)",
            border: `1px solid ${error ? "#ef4444" : "var(--gov-border-strong)"}`,
            borderRadius: "var(--radius-md)",
            outline: "none",
            boxShadow: "var(--shadow-sm)",
            cursor: disabled ? "not-allowed" : "pointer",
            ...style,
          }}
          className={`gov-select ${className}`}
          {...props}
        >
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>

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

Select.displayName = "Select";
