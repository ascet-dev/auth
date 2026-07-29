import type { Me, SessionWithTokens } from "./types";

const REFRESH_KEY = "auth_admin_refresh";
const SESSION_KEY = "auth_admin_session_id";

// Access-токен короткоживущий — держим только в памяти, клиент refresh-driven
let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

// Подписка на окончательную потерю сессии: без неё AuthContext не узнавал бы,
// что токены стёрты, и продолжал рендерить админку вместо редиректа на /login
type SessionLostHandler = () => void;
let onSessionLost: SessionLostHandler | null = null;

export function setSessionLostHandler(handler: SessionLostHandler | null): void {
  onSessionLost = handler;
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    const message =
      body && typeof body === "object" && "message" in body
        ? String((body as { message: unknown }).message)
        : `HTTP ${status}`;
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function parseBody(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  if (res.status === 401 && retry && (await tryRefresh())) {
    return api<T>(path, init, false);
  }
  if (!res.ok) {
    throw new ApiError(res.status, await parseBody(res));
  }
  return (await res.json()) as T;
}

function storeTokens(data: SessionWithTokens): void {
  accessToken = data.access_token;
  localStorage.setItem(REFRESH_KEY, data.refresh_token);
  localStorage.setItem(SESSION_KEY, data.session.id);
}

function clearTokens(): void {
  accessToken = null;
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(SESSION_KEY);
}

export function hasStoredSession(): boolean {
  return localStorage.getItem(REFRESH_KEY) !== null;
}

export async function tryRefresh(): Promise<boolean> {
  // Одновременные 401 не должны устраивать гонку ротации refresh-токена
  refreshPromise ??= doRefresh().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

async function doRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return false;

  const res = await fetch("/admin/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) {
    // Токен отвергнут — сессии конец. Транзиентный сбой (5xx) сессию не рушит:
    // иначе перезапуск бэкенда выкидывал бы на логин.
    if (res.status === 401) {
      // Другая вкладка могла успеть провернуть ротацию — не стираем её свежий токен
      if (localStorage.getItem(REFRESH_KEY) === refreshToken) {
        clearTokens();
        onSessionLost?.();
      }
    }
    return false;
  }
  storeTokens((await res.json()) as SessionWithTokens);
  return true;
}

export async function apiLogin(login: string, password: string): Promise<void> {
  const res = await fetch("/admin/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ login, password }),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseBody(res));
  }
  storeTokens((await res.json()) as SessionWithTokens);
}

export async function apiLogout(): Promise<void> {
  const sessionId = localStorage.getItem(SESSION_KEY);
  if (sessionId) {
    try {
      await api("/auth/session/logout", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch {
      // сессию не удалось ревокнуть (уже истекла и т.п.) — просто чистим локально
    }
  }
  clearTokens();
}

export async function apiMe(): Promise<Me> {
  return api<Me>("/admin/auth/me");
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value));
    }
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}
