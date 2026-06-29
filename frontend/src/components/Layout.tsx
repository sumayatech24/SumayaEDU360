import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { MenuItem } from "../lib/types";
import { Brand } from "./Brand";
import { GlobalSearch } from "./GlobalSearch";
import { Icon } from "./Icon";

/** Logical sidebar grouping: maps a route to its section. Anything unmapped
 *  (e.g. registry-driven `/m/...` modules) falls into "More Modules". */
const GROUP_FOR: Record<string, string> = {
  "/dashboard": "Overview",
  "/academic": "Academics", "/curriculum": "Academics", "/timetable": "Academics",
  "/exams": "Academics", "/promotion": "Academics", "/question-bank": "Academics",
  "/homework": "Academics", "/teacher-allocation": "Academics",
  "/students": "Students & Admissions", "/admissions": "Students & Admissions", "/attendance": "Students & Admissions",
  "/employees": "Staff & HR", "/hr": "Staff & HR", "/payroll": "Staff & HR",
  "/engagement": "Engagement & Communication", "/communication": "Engagement & Communication",
  "/parent-portal": "Engagement & Communication", "/cms": "Engagement & Communication",
  "/knowledge": "Engagement & Communication", "/activities": "Engagement & Communication",
  "/library": "Operations", "/hostel": "Operations", "/transport": "Operations",
  "/meals": "Operations", "/store": "Operations", "/asset-tracking": "Operations",
  "/fees": "Finance", "/finance": "Finance",
  "/reports": "Insights", "/ai": "Insights",
  "/masters": "Configuration", "/branding": "Configuration", "/customize-fields": "Configuration",
  "/users": "Configuration", "/audit": "Configuration", "/integrations": "Configuration",
};
const GROUP_ORDER = [
  "Overview", "Academics", "Students & Admissions", "Staff & HR",
  "Engagement & Communication", "Operations", "Finance", "Insights",
  "Configuration", "More Modules",
];
const groupOf = (path: string) => GROUP_FOR[path] ?? "More Modules";

export function Layout() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const { data: menu = [] } = useQuery({
    queryKey: ["navigation"],
    queryFn: async () => (await api.get<MenuItem[]>("/navigation")).data,
  });

  // Combine DB-driven menu with statically-routed pages, then bucket into groups.
  const items: MenuItem[] = [...menu];
  if (!items.some((m) => m.path === "/engagement")) {
    items.push({ id: "static-engagement", path: "/engagement", icon: "users", label: "Family Engagement", sort_order: 0 });
  }
  if (!items.some((m) => m.path === "/payroll")) {
    items.push({ id: "static-payroll", path: "/payroll", icon: "credit-card", label: "Payroll", sort_order: 0 });
  }
  const grouped = new Map<string, MenuItem[]>();
  GROUP_ORDER.forEach((g) => grouped.set(g, []));
  items.forEach((m) => {
    const g = groupOf(m.path);
    if (!grouped.has(g)) grouped.set(g, []);
    grouped.get(g)!.push(m);
  });

  return (
    <div className="flex h-full">
      <aside className="flex w-64 flex-col border-r border-slate-200 bg-white">
        <div className="px-5 py-4">
          <Brand size={36} />
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-6">
          {GROUP_ORDER.map((label) => {
            const groupItems = grouped.get(label) ?? [];
            if (groupItems.length === 0) return null;
            const hasActive = groupItems.some(
              (m) => location.pathname === m.path || location.pathname.startsWith(m.path + "/"),
            );
            return <NavGroup key={label} label={label} items={groupItems} hasActive={hasActive} />;
          })}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div className="flex items-center gap-3">
            <button className="btn-ghost text-sm" onClick={() => navigate(-1)}>
              ← Back
            </button>
            <GlobalSearch />
          </div>
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

/** A collapsible sidebar section; open/closed state persists per group. */
function NavGroup({ label, items, hasActive }: { label: string; items: MenuItem[]; hasActive: boolean }) {
  const storeKey = `nav.group.${label}`;
  const [open, setOpen] = useState<boolean>(() => {
    const saved = localStorage.getItem(storeKey);
    return saved === null ? true : saved === "1";
  });
  // Always reveal the section that contains the active route.
  const expanded = open || hasActive;
  useEffect(() => {
    localStorage.setItem(storeKey, open ? "1" : "0");
  }, [open, storeKey]);

  return (
    <div className="pt-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-md px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-600"
      >
        <span>{label}</span>
        <svg
          className={`transition-transform ${expanded ? "rotate-90" : ""}`}
          width="12" height="12" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
        >
          <path d="M9 18l6-6-6-6" />
        </svg>
      </button>
      {expanded && items.map((m) => <NavItem key={m.id} to={m.path} icon={m.icon} label={m.label} />)}
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
