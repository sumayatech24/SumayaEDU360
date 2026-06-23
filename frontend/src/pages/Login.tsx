import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiError } from "../lib/api";
import { PORTAL_BASE, useAuth } from "../lib/auth";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@sumaya.edu");
  const [password, setPassword] = useState("Admin@123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const ctx = await login(email, password);
      navigate(PORTAL_BASE[ctx.portal] ?? "/");
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center bg-gradient-to-br from-brand-600 to-brand-900 p-6">
      <div className="card w-full max-w-md p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-lg font-bold text-white">
            S
          </div>
          <div>
            <div className="text-lg font-bold">SumayaEDU360</div>
            <div className="text-xs text-slate-400">AI EduOS — Education ERP</div>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Email</label>
            <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
          <button className="btn-primary w-full" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-5 border-t border-slate-100 pt-3">
          <p className="mb-2 text-center text-[11px] font-medium uppercase tracking-wide text-slate-400">
            Demo logins — one per portal
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Admin", "admin@sumaya.edu", "Admin@123"],
              ["Teacher", "teacher@sumaya.edu", "Teacher@123"],
              ["Student", "student@sumaya.edu", "Student@123"],
              ["Parent", "parent@sumaya.edu", "Parent@123"],
            ].map(([role, em, pw]) => (
              <button
                key={role}
                type="button"
                onClick={() => {
                  setEmail(em);
                  setPassword(pw);
                }}
                className="rounded-lg border border-slate-200 px-2 py-1.5 text-left hover:border-brand-400 hover:bg-brand-50"
              >
                <div className="font-medium text-slate-700">{role}</div>
                <div className="truncate text-[10px] text-slate-400">{em}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
