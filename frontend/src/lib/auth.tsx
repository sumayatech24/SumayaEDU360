import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";
import type { Me } from "./types";

interface AuthCtx {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (perm: string) => boolean;
}

const Ctx = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get<Me>("/auth/me");
      setMe(data);
    } catch {
      setToken(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMe();
  }, []);

  async function login(email: string, password: string) {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const { data } = await api.post<{ access_token: string }>("/auth/login", form);
    setToken(data.access_token);
    const { data: meData } = await api.get<Me>("/auth/me");
    setMe(meData);
  }

  function logout() {
    setToken(null);
    setMe(null);
    location.href = "/login";
  }

  function can(perm: string): boolean {
    if (!me) return false;
    if (me.is_superadmin || me.permissions.includes("*")) return true;
    if (me.permissions.includes(perm)) return true;
    const mod = perm.split(":")[0];
    return me.permissions.includes(`${mod}:*`);
  }

  return <Ctx.Provider value={{ me, loading, login, logout, can }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  return useContext(Ctx);
}
