/**
 * Centralized Navigation Configuration for CRPF Tender Evaluation System.
 * Defines hierarchical navigation groups, canonical route paths, icons,
 * and associated RBAC permissions.
 */

import type { PermissionName, RoleName } from "@/types/auth";

export interface NavItemConfig {
  id: string;
  label: string;
  href: string;
  iconName: "dashboard" | "tenders" | "bidders" | "evaluations" | "reviews" | "reports" | "audit";
  requiredPermission?: PermissionName;
  requiredRole?: RoleName;
  badge?: string;
  exactMatch?: boolean;
}

export interface NavGroupConfig {
  id: string;
  title: string;
  items: NavItemConfig[];
}

export const NAVIGATION_GROUPS: NavGroupConfig[] = [
  {
    id: "main",
    title: "MAIN",
    items: [
      {
        id: "dashboard",
        label: "Dashboard",
        href: "/dashboard",
        iconName: "dashboard",
      },
    ],
  },
  {
    id: "procurement",
    title: "PROCUREMENT",
    items: [
      {
        id: "tenders",
        label: "Tenders",
        href: "/tenders",
        iconName: "tenders",
        requiredPermission: "TENDER_READ",
      },
      {
        id: "bidders",
        label: "Bidders",
        href: "/bidders",
        iconName: "bidders",
        requiredPermission: "BIDDER_READ",
      },
    ],
  },
  {
    id: "evaluation",
    title: "EVALUATION",
    items: [
      {
        id: "evaluations",
        label: "Evaluations",
        href: "/evaluations",
        iconName: "evaluations",
        requiredPermission: "EVALUATION_READ",
      },
      {
        id: "reviews",
        label: "Reviews",
        href: "/reviews",
        iconName: "reviews",
        requiredPermission: "REVIEW_CREATE",
      },
    ],
  },
  {
    id: "reporting",
    title: "REPORTING",
    items: [
      {
        id: "reports",
        label: "Reports",
        href: "/reports",
        iconName: "reports",
        requiredPermission: "REPORT_READ",
      },
    ],
  },
  {
    id: "system",
    title: "SYSTEM",
    items: [
      {
        id: "audit",
        label: "Audit Trail",
        href: "/audit",
        iconName: "audit",
        requiredPermission: "USER_MANAGE",
      },
    ],
  },
];

export const BIDDER_NAVIGATION_GROUPS: NavGroupConfig[] = [
  {
    id: "bidder-portal",
    title: "BIDDER PORTAL",
    items: [
      {
        id: "bidder-dashboard",
        label: "Dashboard",
        href: "/bidder/dashboard",
        iconName: "dashboard",
      },
      {
        id: "bidder-tenders",
        label: "Browse Tenders",
        href: "/tenders/public",
        iconName: "tenders",
      },
      {
        id: "bidder-applications",
        label: "My Applications",
        href: "/bidder/applications",
        iconName: "bidders",
      },
      {
        id: "bidder-profile",
        label: "Corporate Profile",
        href: "/bidder/profile",
        iconName: "evaluations",
      },
    ],
  },
];

/**
 * Check whether a target navigation link should be marked active given the current pathname.
 * Handles nested routes (e.g. /tenders/123/documents highlights /tenders)
 * while ensuring / is not falsely matched by all paths.
 */
export function isRouteActive(itemHref: string, currentPathname: string, exactMatch: boolean = false): boolean {
  if (!currentPathname) return false;
  if (exactMatch || itemHref === "/") {
    return currentPathname === itemHref;
  }
  return currentPathname === itemHref || currentPathname.startsWith(`${itemHref}/`);
}
