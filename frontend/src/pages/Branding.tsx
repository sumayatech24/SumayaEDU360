import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, apiError } from "../lib/api";
import type { Branding as B } from "../lib/branding";

export function Branding() {
  const qc = useQueryClient();
  const [form, setForm] = useState<B>({ institution_name: "", logo_url: "", tagline: "", primary_color: "#2563eb", address: "", phone: "", email: "", website: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const { data } = useQuery({
    queryKey: ["branding-me"],
    queryFn: async () => (await api.get<B>("/branding/me")).data,
  });
  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  function onLogoFile(file?: File) {
    if (!file) return;
    if (file.size > 400_000) {
      setError("Please use an image under 400 KB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setForm((f) => ({ ...f, logo_url: String(reader.result) }));
    reader.readAsDataURL(file);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const entries: [string, string][] = [
        ["branding.institution_name", form.institution_name],
        ["branding.logo_url", form.logo_url],
        ["branding.tagline", form.tagline],
        ["branding.primary_color", form.primary_color],
        ["branding.address", form.address ?? ""],
        ["branding.phone", form.phone ?? ""],
        ["branding.email", form.email ?? ""],
        ["branding.website", form.website ?? ""],
      ];
      for (const [key, value] of entries) {
        await api.put(`/settings/${key}`, { key, value_json: { value }, data_type: "string" });
      }
      qc.invalidateQueries({ queryKey: ["branding"] });
      qc.invalidateQueries({ queryKey: ["branding-me"] });
      setMsg("Branding saved — it now appears across login and every portal.");
    } catch (e) {
      setError(apiError(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Branding</h1>
        <p className="text-sm text-slate-400">
          Your institution logo and name appear on the login screen, admin header and every portal.
        </p>
      </div>

      <div className="card space-y-4 p-6">
        <div className="flex items-center gap-4">
          {form.logo_url ? (
            <img src={form.logo_url} alt="" className="h-16 w-16 rounded-xl border border-slate-200 object-contain" />
          ) : (
            <div
              className="flex h-16 w-16 items-center justify-center rounded-xl font-bold text-white"
              style={{ background: form.primary_color }}
            >
              {form.institution_name[0] || "S"}
            </div>
          )}
          <div className="flex-1">
            <label className="label">Logo (PNG/SVG, &lt; 400 KB)</label>
            <input type="file" accept="image/*" className="text-sm" onChange={(e) => onLogoFile(e.target.files?.[0])} />
            <input
              className="input mt-2"
              placeholder="…or paste a logo URL / data URI"
              value={form.logo_url}
              onChange={(e) => setForm({ ...form, logo_url: e.target.value })}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Institution Name</label>
            <input className="input" value={form.institution_name} onChange={(e) => setForm({ ...form, institution_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Tagline</label>
            <input className="input" value={form.tagline} onChange={(e) => setForm({ ...form, tagline: e.target.value })} />
          </div>
          <div>
            <label className="label">Primary Colour</label>
            <input type="color" className="input h-10 w-20 p-1" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} />
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <h2 className="text-sm font-semibold text-slate-600">Report header & footer</h2>
          <p className="mb-3 text-xs text-slate-400">The logo above and these details appear on every printed report, marksheet and receipt — address shows at the bottom of each page.</p>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="label">School Address</label>
              <textarea className="input min-h-16" value={form.address ?? ""} onChange={(e) => setForm({ ...form, address: e.target.value })} placeholder="123 School Road, City, State — PIN" />
            </div>
            <div>
              <label className="label">Phone</label>
              <input className="input" value={form.phone ?? ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input" value={form.email ?? ""} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="col-span-2">
              <label className="label">Website</label>
              <input className="input" value={form.website ?? ""} onChange={(e) => setForm({ ...form, website: e.target.value })} />
            </div>
          </div>
        </div>

        {msg && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
        {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

        <button className="btn-primary" disabled={saving} onClick={save}>
          {saving ? "Saving…" : "Save Branding"}
        </button>
      </div>
    </div>
  );
}
