export type UUID = string;

export interface Pagination {
  limit: number | null;
  offset: number;
  total: number;
}

export interface Paginated<T> {
  items: T[];
  pagination: Pagination;
}

export interface SessionInfo {
  id: UUID;
  identity_id: UUID;
  client_app_id: UUID;
  refresh_expires_at: string;
  status: string | null;
  last_used_at: string | null;
  ip: string | null;
  user_agent: string | null;
  device_id: string | null;
  created?: string | null;
  updated?: string | null;
}

export interface SessionWithTokens {
  session: SessionInfo & { [k: string]: unknown };
  access_token: string;
  refresh_token: string;
}

export interface Me {
  identity_id: UUID;
  role: "OWNER" | "ADMIN";
}

export interface ClientApp {
  id: UUID;
  key: string;
  name: string;
  type: string | null;
  allowed_redirect_uris: string[] | null;
  allowed_scopes: string[] | null;
  allowed_auth_methods: string[] | null;
  access_token_ttl_sec: number;
  refresh_token_ttl_sec: number;
  created?: string | null;
  archived?: boolean | null;
}

export interface AuthMethodConfig {
  method: "PASSWORD" | "OTP" | "TMA" | "OAUTH";
  enabled: boolean;
  configured: boolean;
  allow_registration: boolean | null;
  bot_token_set: boolean;
  env_bot_token_set: boolean;
  auth_date_max_age: number | null;
}

export interface OauthProvider {
  id: UUID;
  name: string;
  client_id: string;
  auth_url: string;
  token_url: string;
  jwks_url: string | null;
  userinfo_url: string | null;
  enabled: boolean;
  client_secret_set: boolean;
  created?: string | null;
  archived?: boolean | null;
}

export interface Identity {
  id: UUID;
  tenant_id: string | null;
  status: string | null;
  created?: string | null;
  archived?: boolean | null;
}

export interface CredentialSummary {
  id: UUID;
  type: string | null;
  identifier: string | null;
  provider: string | null;
  external_subject_id: string | null;
  last_used: string | null;
}

export interface Grant {
  id: UUID;
  identity_id: UUID;
  role: "OWNER" | "ADMIN";
  granted_by: UUID | null;
  created?: string | null;
  archived?: boolean | null;
}

export interface IdentityDetail {
  identity: Identity;
  credentials: CredentialSummary[];
  external_links: { id: UUID; external_system: string; external_user_id: string }[];
  grant: Grant | null;
}

export interface LoginRecord {
  id: UUID;
  method: string;
  identifier: string | null;
  identity_id: UUID | null;
  credential_id: UUID | null;
  success: boolean;
  ip_address: string | null;
  user_agent: string | null;
  created?: string | null;
}
