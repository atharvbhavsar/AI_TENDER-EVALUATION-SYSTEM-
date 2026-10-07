"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbsProps {
  items?: BreadcrumbItem[];
  showHome?: boolean;
  className?: string;
}

function formatSegment(segment: string): string {
  if (!segment) return "";
  return segment
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function Breadcrumbs({ items, showHome = true, className = "" }: BreadcrumbsProps) {
  const pathname = usePathname();

  // If no items provided, compute them automatically from URL pathname
  let computedItems: BreadcrumbItem[] = [];

  if (items && items.length > 0) {
    computedItems = items;
  } else if (pathname && pathname !== "/") {
    const segments = pathname.split("/").filter(Boolean);
    let currentPath = "";

    computedItems = segments.map((seg, idx) => {
      currentPath += `/${seg}`;
      const isLast = idx === segments.length - 1;
      return {
        label: formatSegment(seg),
        href: isLast ? undefined : currentPath,
      };
    });
  } else {
    computedItems = [{ label: "Dashboard" }];
  }

  // Prepend Home / Dashboard if requested and not already first item
  const finalItems: BreadcrumbItem[] = [];
  if (showHome && (computedItems.length === 0 || computedItems[0].label !== "Dashboard")) {
    finalItems.push({ label: "Dashboard", href: "/dashboard" });
  }
  finalItems.push(...computedItems);

  return (
    <nav
      aria-label="Breadcrumb"
      style={{
        fontSize: "12px",
        color: "var(--gov-text-muted)",
        marginBottom: "12px",
      }}
      className={`gov-breadcrumbs ${className}`}
    >
      <ol
        style={{
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "6px",
          margin: 0,
          padding: 0,
          listStyle: "none",
        }}
      >
        {finalItems.map((item, idx) => {
          const isLast = idx === finalItems.length - 1;
          return (
            <li
              key={idx}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              {idx > 0 && (
                <span
                  aria-hidden="true"
                  style={{
                    color: "var(--gov-border-dark)",
                    fontSize: "11px",
                    userSelect: "none",
                  }}
                >
                  /
                </span>
              )}

              {!isLast && item.href ? (
                <Link
                  href={item.href}
                  style={{
                    color: "var(--gov-text-secondary)",
                    textDecoration: "none",
                    fontWeight: 500,
                  }}
                  className="hover:underline"
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  aria-current={isLast ? "page" : undefined}
                  style={{
                    color: isLast ? "var(--gov-text-primary)" : "var(--gov-text-secondary)",
                    fontWeight: isLast ? 600 : 500,
                  }}
                >
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
