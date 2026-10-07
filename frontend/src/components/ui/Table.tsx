import React from "react";

export interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  children: React.ReactNode;
  dense?: boolean;
}

export function Table({
  children,
  dense = false,
  className = "",
  style,
  ...props
}: TableProps) {
  return (
    <div
      style={{
        width: "100%",
        overflowX: "auto",
        border: "1px solid var(--gov-border)",
        borderRadius: "var(--radius-lg)",
        backgroundColor: "var(--gov-surface)",
      }}
      tabIndex={0}
      role="region"
      aria-label="Data table"
    >
      <table
        className={`gov-table ${dense ? "gov-table-dense" : ""} ${className}`}
        style={style}
        {...props}
      >
        {children}
      </table>
    </div>
  );
}
