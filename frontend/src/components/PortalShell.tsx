import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useBranding } from "../lib/branding";
import { Icon } from "./Icon";

export interface PortalNavItem {
  label: string;
  icon: string;
  to: string;
}

const THEMES: Record<string, { from: string; chip: string; tag: string }> = {
  student: { from: "from-indigo-600 to-indigo-800", chip: "bg-indigo-600", tag: "Student Portal" },
  parent: { from: "from-emerald-600 to-emerald-800", chip: "bg-emerald-600", tag: "Parent Portal" },
  teacher: { from: "from-orange-600 to-orange-800", chip: "bg-orange-600", tag: "Teacher Portal" },
  principal: { from: "from-slate-700 to-slate-900", chip: "bg-slate-700", tag: "Principal Portal" },
};

export function PortalShell({
  portal,
  nav,
  children,
}: {
  portal: "student" | "parent" | "teacher" | "principal";
  nav: PortalNavItem[];
  children: ReactNode;
}) {
  const { portal: ctx, logout } = useAuth();
  const b = useBranding();
  const theme = THEMES[portal];

  return (
    <div className="flex h-full flex-col">
      <header className={`bg-gradient-to-r ${theme.from} text-white`}>
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            {b.logo_url ? (
              <img src={b.logo_url} alt="" className="h-10 w-10 rounded-xl object-contain bg-white/10 p-0.5" />
            ) : (
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${theme.chip} font-bold`}>
                {b.institution_name[0]}
              </div>
            )}
            <div>
              <div className="text-sm font-bold leading-tight">{b.institution_name}</div>
              <div className="text-[11px] text-white/70">{theme.tag}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-medium">{ctx?.name}</div>
              <div className="text-[11px] text-white/70">{ctx?.email}</div>
            </div>
            <button className="rounded-lg bg-white/15 px-3 py-1.5 text-sm hover:bg-white/25" onClick={logout}>
              Logout
            </button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 px-4">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === ""}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-t-lg px-4 py-2.5 text-sm transition ${
                  isActive ? "bg-slate-100 font-medium text-slate-800" : "text-white/85 hover:bg-white/10"
                }`
              }
            >
              <Icon name={n.icon} />
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1 overflow-y-auto bg-slate-100">
        <div className="mx-auto max-w-6xl p-6">{children}</div>
      </main>
    </div>
  );
}
