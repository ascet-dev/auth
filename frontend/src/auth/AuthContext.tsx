import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { apiLogin, apiLogout, apiMe, hasStoredSession, setSessionLostHandler, tryRefresh } from "../api/client";
import type { Me } from "../api/types";

interface AuthState {
  loading: boolean;
  me: Me | null;
  login: (login: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    // Сессия окончательно потеряна (refresh отвергнут) → уводим на логин
    setSessionLostHandler(() => setMe(null));
    return () => setSessionLostHandler(null);
  }, []);

  useEffect(() => {
    // boot: есть refresh-токен → пробуем восстановить сессию
    (async () => {
      try {
        if (hasStoredSession() && (await tryRefresh())) {
          setMe(await apiMe());
        }
      } catch {
        setMe(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = useCallback(async (loginValue: string, password: string) => {
    await apiLogin(loginValue, password);
    setMe(await apiMe());
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setMe(null);
  }, []);

  const value = useMemo(() => ({ loading, me, login, logout }), [loading, me, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
