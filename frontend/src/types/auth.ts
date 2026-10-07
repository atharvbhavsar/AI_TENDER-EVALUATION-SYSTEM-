/**
 * Authentication and authorization types mirroring backend schemas.
 * (app/auth/schemas.py, app/auth/service.py, and app/db/models/user.py)
 */

export type RoleName =
  | "ADMIN"
  | "PROCUREMENT_OFFICER"
  | "REVIEWER"
  | "BIDDER"
  | string;

export type PermissionName =
  | "USER_READ"
  | "USER_MANAGE"
  | "TENDER_READ"
  | "TENDER_CREATE"
  | "TENDER_UPDATE"
  | "TENDER_APPROVE"
  | "BIDDER_READ"
  | "BIDDER_MANAGE"
  | "DOCUMENT_READ"
  | "DOCUMENT_UPLOAD"
  | "EVIDENCE_READ"
  | "EVALUATION_READ"
  | "REVIEW_CREATE"
  | "REVIEW_APPROVE"
  | "REPORT_READ"
  | string;

export interface Role {
  id: string;
  name: RoleName;
  description?: string | null;
}

export interface Permission {
  id: string;
  name: PermissionName;
  description?: string | null;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  company_name?: string | null;
  phone?: string | null;
  is_active: boolean;
  roles: RoleName[];
  permissions: PermissionName[];
  created_at?: string;
  last_login_at?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterBidderRequest {
  email: string;
  password: string;
  full_name: string;
  company_name: string;
  phone?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  company_name?: string | null;
  phone?: string | null;
  is_active: boolean;
  roles: RoleName[];
  permissions: PermissionName[];
}

export interface AuthContextType {
  currentUser: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterBidderRequest) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  hasPermission: (permission: PermissionName) => boolean;
  hasRole: (role: RoleName) => boolean;
  hasAnyPermission: (permissions: PermissionName[]) => boolean;
  hasAllPermissions: (permissions: PermissionName[]) => boolean;
}
