import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Page } from "../lib/types";

interface Hit {
  id: string;
  label: string;
  sub: string;
  kind: string;
  to: string;
}

/** Header search across students, employees, fee invoices and admission leads. */
export function GlobalSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const { data: hits = [], isFetching } = useQuery({
    enabled: q.trim().length >= 2,
    queryKey: ["global-search", q],
    queryFn: async (): Promise<Hit[]> => {
      const params = { q, page_size: 5 };
      const [students, employees, leads] = await Promise.all([
        api.get<Page<any>>("/students", { params }).then((r) => r.data).catch(() => null),
        api.get<Page<any>>("/employees", { params }).then((r) => r.data).catch(() => null),
        api.get<Page<any>>("/admission-leads", { params }).then((r) => r.data).catch(() => null),
      ]);
      const out: Hit[] = [];
      students?.items.forEach((s) =>
        out.push({ id: s.id, label: `${s.first_name} ${s.last_name ?? ""}`.trim(), sub: `Student · ${s.admission_no}`, kind: "student", to: "/students" })
      );
      employees?.items.forEach((e) =>
        out.push({ id: e.id, label: `${e.first_name} ${e.last_name ?? ""}`.trim(), sub: `Employee · ${e.designation ?? ""}`, kind: "employee", to: "/employees" })
      );
      leads?.items.forEach((l) =>
        out.push({ id: l.id, label: l.student_name, sub: `Admission lead · ${l.stage}`, kind: "lead", to: "/admissions" })
      );
      return out;
    },
  });

  return (
    <div ref={boxRef} className="relative">
      <input
        className="input w-72"
        placeholder="Search students, staff, leads…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && q.trim().length >= 2 && (
        <div className="absolute z-50 mt-1 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
          {isFetching && <div className="px-4 py-3 text-sm text-slate-400">Searching…</div>}
          {!isFetching && hits.length === 0 && <div className="px-4 py-3 text-sm text-slate-400">No matches.</div>}
          {hits.map((h) => (
            <button
              key={h.kind + h.id}
              onClick={() => {
                setOpen(false);
                setQ("");
                navigate(h.to);
              }}
              className="flex w-full flex-col items-start px-4 py-2 text-left hover:bg-slate-50"
            >
              <span className="text-sm font-medium">{h.label}</span>
              <span className="text-[11px] text-slate-400">{h.sub}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
