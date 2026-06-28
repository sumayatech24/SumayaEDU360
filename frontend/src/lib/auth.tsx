import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";
import type { Me } from "./types";

export interface PortalContext {
  portal: "admin" | "student" | "parent" | "teacher";
  name: string;
  email: string;
  roles: string[];
  is_superadmin: boolean;
  person_type?: string | null;
  person_id?: string | null;
}

interface AuthCtx {
  me: Me | null;
  portal: PortalContext | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<PortalContext>;
  logout: () => void;
  can: (perm: string) => boolean;
}

export const PORTAL_BASE: Record<string, string> = {
  admin: "/dashboard",
  student: "/student",
  parent: "/parent",
  teacher: "/teacher",
};

const Ctx = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [portal, setPortal] = useState<PortalContext | null>(null);
  const [loading, setLoading] = useState(true);

  async function hydrate(): Promise<PortalContext> {
    const [{ data: meData }, { data: ctx }] = await Promise.all([
      api.get<Me>("/auth/me"),
      api.get<PortalContext>("/portal/context"),
    ]);
    setMe(meData);
    setPortal(ctx);
    return ctx;
  }

  async function loadMe() {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    try {
      await hydrate();
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
    return hydrate();
  }

  function logout() {
    setToken(null);
    setMe(null);
    setPortal(null);
    location.href = "/login";
  }

  function can(perm: string): boolean {
    if (!me) return false;
    if (me.is_superadmin || me.permissions.includes("*")) return true;
    if (me.permissions.includes(perm)) return true;
    const mod = perm.split(":")[0];
    return me.permissions.includes(`${mod}:*`);
  }

  return <Ctx.Provider value={{ me, portal, loading, login, logout, can }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  return useContext(Ctx);
}
