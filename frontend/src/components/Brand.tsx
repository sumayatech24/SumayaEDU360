import { useBranding } from "../lib/branding";

/** Logo + institution name, used in login, admin header and all portal headers. */
export function Brand({
  size = 36,
  light = false,
  showTagline = true,
}: {
  size?: number;
  light?: boolean;
  showTagline?: boolean;
}) {
  const b = useBranding();
  return (
    <div className="flex items-center gap-2.5">
      {b.logo_url ? (
        <img
          src={b.logo_url}
          alt=""
          style={{ width: size, height: size }}
          className="rounded-lg object-contain"
        />
      ) : (
        <div
          style={{ width: size, height: size, background: b.primary_color }}
          className="flex items-center justify-center rounded-lg font-bold text-white"
        >
          {b.institution_name[0]}
        </div>
      )}
      <div className="leading-tight">
        <div className={`text-sm font-bold ${light ? "text-white" : ""}`}>{b.institution_name}</div>
        {showTagline && (
          <div className={`text-[11px] ${light ? "text-white/70" : "text-slate-400"}`}>{b.tagline}</div>
        )}
      </div>
    </div>
  );
}
