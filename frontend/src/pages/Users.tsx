import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiError } from "../lib/api";
import { Modal } from "../components/Modal";
import { SearchBox } from "../components/SearchBox";
import { filterByQuery } from "../lib/search";

interface Role {
  id: string;
  code: string;
  name: string;
}
interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superadmin: boolean;
  roles: Role[];
}

export function Users() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role_codes: [] as string[] });
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get<User[]>("/users")).data,
  });
  const { data: roles = [] } = useQuery({
    queryKey: ["roles"],
    queryFn: async () => (await api.get<Role[]>("/roles")).data,
  });

  const create = useMutation({
    mutationFn: async () => api.post("/users", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setOpen(false);
      setForm({ email: "", full_name: "", password: "", role_codes: [] });
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Users & Roles</h1>
          <p className="text-sm text-slate-400">{roles.length} roles loaded from the RBAC matrix.</p>
        </div>
        <div className="flex items-center gap-2">
          <SearchBox value={search} onChange={setSearch} placeholder="Search users…" />
          <button className="btn-primary" onClick={() => setOpen(true)}>
            + New User
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Roles</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filterByQuery(users, search).map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{u.full_name}</td>
                <td className="px-4 py-3">{u.email}</td>
                <td className="px-4 py-3">
                  {u.is_superadmin ? (
                    <span className="badge bg-brand-50 text-brand-700">Super Admin</span>
                  ) : (
                    u.roles.map((r) => (
                      <span key={r.id} className="badge mr-1 bg-slate-100 text-slate-600">
                        {r.name}
                      </span>
                    ))
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`badge ${u.is_active ? "bg-emerald-50 text-emerald-600" : "bg-slate-100"}`}>
                    {u.is_active ? "active" : "inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && (
        <Modal title="New User" onClose={() => setOpen(false)}>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Full Name</label>
                <input
                  className="input"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                />
              </div>
              <div>
                <label className="label">Email</label>
                <input
                  className="input"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </div>
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password"
                className="input"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <div>
              <label className="label">Roles</label>
              <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
                {roles.map((r) => {
                  const on = form.role_codes.includes(r.code);
                  return (
                    <button
                      key={r.id}
                      onClick={() =>
                        setForm({
                          ...form,
                          role_codes: on
                            ? form.role_codes.filter((c) => c !== r.code)
                            : [...form.role_codes, r.code],
                        })
                      }
                      className={`badge ${on ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"}`}
                    >
                      {r.name}
                    </button>
                  );
                })}
              </div>
            </div>
            {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button className="btn-primary" disabled={create.isPending} onClick={() => create.mutate()}>
                Create
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
