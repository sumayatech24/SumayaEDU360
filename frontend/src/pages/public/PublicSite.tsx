import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { publicApi } from "../../lib/api";

const SITE_CODE = "SUMAYA";

interface SiteData {
  branding: { institution_name: string; logo_url: string; tagline: string; primary_color: string };
  institution?: { name: string; board?: string; address?: string } | null;
  banners: { title: string; image_url?: string; link_url?: string }[];
  pages: { title: string; slug: string }[];
  news: { title: string; slug: string; type: string; date?: string; excerpt: string }[];
}

function Header({ data }: { data?: SiteData }) {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link to="/" className="flex items-center gap-2.5">
          {data?.branding.logo_url ? (
            <img src={data.branding.logo_url} alt="" className="h-9 w-9 rounded-lg object-contain" />
          ) : (
            <div className="h-9 w-9 rounded-lg bg-brand-600" />
          )}
          <span className="text-sm font-bold">{data?.branding.institution_name ?? "School"}</span>
        </Link>
        <nav className="hidden items-center gap-5 text-sm text-slate-600 md:flex">
          {data?.pages.map((p) => (
            <Link key={p.slug} to={`/page/${p.slug}`} className="hover:text-brand-700">
              {p.title}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link to={`/apply/${SITE_CODE}`} className="btn-primary text-sm">
            Apply
          </Link>
          <Link to="/login" className="btn-ghost text-sm">
            Login
          </Link>
        </div>
      </div>
    </header>
  );
}

export function PublicSite() {
  const { data } = useQuery({
    queryKey: ["public-site"],
    queryFn: async () => (await publicApi.get<SiteData>(`/public/site/${SITE_CODE}`)).data,
  });
  const color = data?.branding.primary_color ?? "#2563eb";

  return (
    <div className="min-h-full bg-slate-50">
      <Header data={data} />

      {/* Hero */}
      <section className="text-white" style={{ background: `linear-gradient(135deg, ${color}, #0f172a)` }}>
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="max-w-2xl">
            <div className="mb-3 text-sm font-medium uppercase tracking-wide text-white/70">
              {data?.institution?.board ?? "CBSE"} · {data?.branding.tagline}
            </div>
            <h1 className="text-4xl font-bold leading-tight md:text-5xl">
              {data?.branding.institution_name ?? "Welcome"}
            </h1>
            <p className="mt-4 text-lg text-white/85">
              Nurturing curious minds with academic excellence, sports, arts and values — from
              Nursery to Grade 12.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to={`/apply/${SITE_CODE}`} className="rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-slate-900 hover:bg-slate-100">
                Apply for Admission
              </Link>
              <Link to="/login" className="rounded-lg bg-white/15 px-5 py-2.5 text-sm font-semibold hover:bg-white/25">
                Student / Parent Login
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Banners / highlights */}
      {(data?.banners.length ?? 0) > 0 && (
        <section className="mx-auto max-w-6xl px-6 py-8">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {data!.banners.map((b, i) => (
              <a
                key={i}
                href={b.link_url ?? undefined}
                className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-white" style={{ background: color }}>
                  ★
                </div>
                <div className="text-sm font-medium">{b.title}</div>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* News & Events */}
      <section className="mx-auto max-w-6xl px-6 py-8">
        <h2 className="mb-4 text-xl font-semibold">News &amp; Events</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {data?.news.map((n) => (
            <Link key={n.slug} to={`/page/${n.slug}`} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow">
              <span className="badge bg-brand-50 capitalize text-brand-700">{n.type}</span>
              <div className="mt-2 font-semibold">{n.title}</div>
              <div className="mt-1 text-xs text-slate-400">{n.date}</div>
              <p className="mt-2 text-sm text-slate-500">{n.excerpt}</p>
            </Link>
          ))}
          {(data?.news.length ?? 0) === 0 && <p className="text-sm text-slate-400">No news yet.</p>}
        </div>
      </section>

      {/* Quick links to pages */}
      <section className="mx-auto max-w-6xl px-6 pb-12">
        <div className="flex flex-wrap gap-3">
          {data?.pages.map((p) => (
            <Link key={p.slug} to={`/page/${p.slug}`} className="rounded-full border border-slate-200 bg-white px-4 py-1.5 text-sm hover:border-brand-400">
              {p.title}
            </Link>
          ))}
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-6 text-sm text-slate-500">
          <div className="font-medium text-slate-700">{data?.branding.institution_name}</div>
          <div className="mt-1">{data?.institution?.address}</div>
          <div className="mt-2 text-xs text-slate-400">Powered by SumayaEDU360</div>
        </div>
      </footer>
    </div>
  );
}
