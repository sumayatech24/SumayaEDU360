import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { MenuItem } from "../lib/types";
import { Icon } from "./Icon";

export function Layout() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();

  const { data: menu = [] } = useQuery({
    queryKey: ["navigation"],
    queryFn: async () => (await api.get<MenuItem[]>("/navigation")).data,
  });

  const core = menu.filter((m) => !m.path.startsWith("/m/"));
  const modules = menu.filter((m) => m.path.startsWith("/m/"));

  return (
    <div className="flex h-full">
      <aside className="flex w-64 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 font-bold text-white">
            S
          </div>
          <div>
            <div className="text-sm font-bold leading-tight">SumayaEDU360</div>
            <div className="text-[11px] text-slate-400">AI EduOS</div>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-6">
          <SectionLabel>Workspace</SectionLabel>
          {core.map((m) => (
            <NavItem key={m.id} to={m.path} icon={m.icon} label={m.label} />
          ))}

          <SectionLabel>All Modules ({modules.length})</SectionLabel>
          {modules.map((m) => (
            <NavItem key={m.id} to={m.path} icon={m.icon} label={m.label} />
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <button className="btn-ghost text-sm" onClick={() => navigate(-1)}>
            ← Back
          </button>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-medium">{me?.full_name}</div>
              <div className="text-[11px] text-slate-400">
                {me?.is_superadmin ? "Super Admin" : me?.roles.map((r) => r.name).join(", ")}
              </div>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
              {me?.full_name?.[0] ?? "?"}
            </div>
            <button className="btn-ghost" title="Logout" onClick={logout}>
              <Icon name="logout" />
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
      {children}
    </div>
  );
}

function NavItem({ to, icon, label }: { to: string; icon: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
          isActive ? "bg-brand-50 font-medium text-brand-700" : "text-slate-600 hover:bg-slate-100"
        }`
      }
    >
      <Icon name={icon} className="shrink-0" />
      <span className="truncate">{label}</span>
    </NavLink>
  );
}
