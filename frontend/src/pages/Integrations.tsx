import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";

interface Setting {
  id: string;
  key: string;
  value_json: { enabled?: boolean } | null;
}

const INTEGRATIONS = [
  { key: "whatsapp", name: "WhatsApp", desc: "Send alerts & reminders via WhatsApp Business API" },
  { key: "sms", name: "SMS Gateway", desc: "Transactional SMS to parents and staff" },
  { key: "email", name: "Email (SMTP)", desc: "Email notifications, receipts and reports" },
  { key: "payment_gateway", name: "Payment Gateway", desc: "Online fee collection (cards/netbanking)" },
  { key: "upi", name: "UPI", desc: "Collect fees via UPI intent / QR" },
  { key: "biometric", name: "Biometric Devices", desc: "Attendance from fingerprint/face devices" },
  { key: "rfid", name: "RFID / QR", desc: "Card/QR based attendance and library" },
  { key: "google_sso", name: "Google SSO", desc: "Single sign-on with Google Workspace" },
  { key: "microsoft_sso", name: "Microsoft SSO", desc: "Single sign-on with Microsoft 365" },
  { key: "video_meeting", name: "Video Meeting", desc: "PTM & online classes (Zoom/Meet/Teams)" },
];

export function Integrations() {
  const qc = useQueryClient();

  const { data: settings = [] } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => (await api.get<Setting[]>("/settings")).data,
  });

  const byKey = (k: string) => settings.find((s) => s.key === `integration.${k}`);

  const toggle = useMutation({
    mutationFn: async ({ key, enabled }: { key: string; enabled: boolean }) =>
      api.put(`/settings/integration.${key}`, {
        key: `integration.${key}`,
        value_json: { enabled },
        module_slug: "integrations",
        data_type: "json",
        description: `Integration toggle for ${key}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Integrations</h1>
        <p className="text-sm text-slate-400">
          Enable third-party channels and providers. Toggles are stored as tenant configuration.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {INTEGRATIONS.map((it) => {
          const enabled = byKey(it.key)?.value_json?.enabled ?? false;
          return (
            <div key={it.key} className="card flex flex-col gap-3 p-5">
              <div className="flex items-start justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-sm font-bold text-brand-700">
                  {it.name[0]}
                </div>
                <span className={`badge ${enabled ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"}`}>
                  {enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
              <div>
                <div className="font-medium">{it.name}</div>
                <p className="text-xs text-slate-400">{it.desc}</p>
              </div>
              <button
                className={enabled ? "btn-ghost" : "btn-primary"}
                disabled={toggle.isPending}
                onClick={() => toggle.mutate({ key: it.key, enabled: !enabled })}
              >
                {enabled ? "Disable" : "Enable"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
