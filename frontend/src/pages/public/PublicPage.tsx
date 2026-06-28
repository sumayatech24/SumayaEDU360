import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { publicApi } from "../../lib/api";

const SITE_CODE = "SUMAYA";

export function PublicPage() {
  const { slug = "" } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["public-page", slug],
    queryFn: async () => (await publicApi.get<any>(`/public/site/${SITE_CODE}/page/${slug}`)).data,
  });

  return (
    <div className="min-h-full bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            {data?.branding?.logo_url && (
              <img src={data.branding.logo_url} alt="" className="h-8 w-8 rounded-lg object-contain" />
            )}
            <span className="text-sm font-bold">{data?.branding?.institution_name ?? "Home"}</span>
          </Link>
          <Link to="/" className="btn-ghost text-sm">← Home</Link>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-6 py-10">
        {isLoading && <p className="text-slate-400">Loading…</p>}
        {isError && <p className="text-slate-400">Page not found.</p>}
        {data && (
          <article>
            <span className="badge bg-brand-50 capitalize text-brand-700">{data.type}</span>
            <h1 className="mt-2 text-3xl font-bold">{data.title}</h1>
            {data.date && <div className="mt-1 text-sm text-slate-400">{data.date}</div>}
            <div className="prose mt-6 whitespace-pre-wrap text-slate-700">{data.body}</div>
          </article>
        )}
      </div>
    </div>
  );
}
