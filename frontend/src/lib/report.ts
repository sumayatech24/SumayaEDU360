// Shared, framework-agnostic report scaffolding so every printable/exported
// document carries the school logo at the top and the school name + address as
// a footer fixed to the bottom of each printed page.

export interface ReportBrand {
  institution_name: string;
  logo_url?: string;
  tagline?: string;
  primary_color?: string;
  address?: string;
  phone?: string;
  email?: string;
  website?: string;
}

export function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function headerHtml(brand: ReportBrand, subtitle?: string): string {
  const accent = brand.primary_color || "#2563eb";
  const logo = brand.logo_url
    ? `<img src="${esc(brand.logo_url)}" alt="" class="rpt-logo"/>`
    : `<div class="rpt-logo rpt-logo-fallback" style="background:${esc(accent)}">${esc((brand.institution_name || "S")[0])}</div>`;
  return `<header class="rpt-hd" style="border-color:${esc(accent)}">
      ${logo}
      <div class="rpt-hd-text">
        <div class="rpt-name">${esc(brand.institution_name)}</div>
        ${brand.tagline ? `<div class="rpt-tag">${esc(brand.tagline)}</div>` : ""}
        ${subtitle ? `<div class="rpt-sub">${esc(subtitle)}</div>` : ""}
      </div>
    </header>`;
}

function footerHtml(brand: ReportBrand): string {
  const contact = [
    brand.address,
    brand.phone ? `Tel: ${brand.phone}` : "",
    brand.email,
    brand.website,
  ]
    .filter(Boolean)
    .map(esc)
    .join("  ·  ");
  return `<footer class="rpt-ft">
      <div class="rpt-ft-name">${esc(brand.institution_name)}</div>
      ${contact ? `<div class="rpt-ft-line">${contact}</div>` : ""}
    </footer>`;
}

const BASE_CSS = `
  *{box-sizing:border-box}
  @page{ margin:14mm 14mm 26mm; }
  body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#1e293b;margin:0;padding:6px 0 0}
  .rpt-hd{display:flex;align-items:center;gap:14px;border-bottom:2px solid #2563eb;padding-bottom:12px;margin-bottom:16px}
  .rpt-logo{height:56px;width:56px;object-fit:contain;border-radius:10px}
  .rpt-logo-fallback{display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:24px}
  .rpt-name{font-size:19px;font-weight:700}
  .rpt-tag{font-size:12px;color:#64748b}
  .rpt-sub{font-size:13px;color:#334155;margin-top:3px;font-weight:600}
  .rpt-meta{font-size:12px;color:#64748b;margin-bottom:12px}
  table{width:100%;border-collapse:collapse;font-size:12px}
  th,td{padding:6px 9px;border:1px solid #e2e8f0;text-align:left;vertical-align:top}
  th{background:#f8fafc;font-size:10px;text-transform:uppercase;color:#475569}
  tr:nth-child(even) td{background:#fafafa}
  .rpt-ft{position:fixed;bottom:0;left:0;right:0;border-top:1px solid #e2e8f0;padding:7px 14mm;background:#fff;text-align:center}
  .rpt-ft-name{font-size:11px;font-weight:600;color:#334155}
  .rpt-ft-line{font-size:10px;color:#64748b;margin-top:2px}
`;

interface ReportDocOptions {
  brand: ReportBrand;
  title: string;
  /** Inner HTML rendered between the header and the footer. */
  bodyHtml: string;
  /** Small line under the header (e.g. record count / date range). */
  meta?: string;
  landscape?: boolean;
  extraCss?: string;
  autoPrint?: boolean;
}

/** Assemble a complete, print-ready HTML document with branded header + footer. */
export function reportDocument(opts: ReportDocOptions): string {
  const { brand, title, bodyHtml, meta, landscape, extraCss = "", autoPrint = true } = opts;
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title>
    <style>${BASE_CSS}${landscape ? "@page{size:landscape}" : ""}${extraCss}</style>
    </head><body>
      ${headerHtml(brand, title)}
      ${meta ? `<div class="rpt-meta">${esc(meta)}</div>` : ""}
      ${bodyHtml}
      ${footerHtml(brand)}
      ${autoPrint ? "<script>window.onload=function(){window.print();}</script>" : ""}
    </body></html>`;
}

/** Open the assembled document in a new window for printing / save-as-PDF. */
export function openReport(html: string): boolean {
  const w = window.open("", "_blank", "width=1024,height=768");
  if (!w) {
    alert("Allow pop-ups to generate the report / PDF.");
    return false;
  }
  w.document.write(html);
  w.document.close();
  return true;
}
