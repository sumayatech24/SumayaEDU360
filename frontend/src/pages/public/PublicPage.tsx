import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { publicApi } from "../../lib/api";
import { PublicFooter, PublicHeader, SITE_CODE, usePublicSite } from "./PublicSite";

export function PublicPage() {
  const { slug = "" } = useParams();
  const { data: siteData } = usePublicSite();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["public-page", slug],
    queryFn: async () => (await publicApi.get<any>(`/public/site/${SITE_CODE}/page/${slug}`)).data,
  });

  return (
    <div className="min-h-full bg-slate-50">
      <PublicHeader data={siteData} />

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
      <PublicFooter data={siteData} />
    </div>
  );
}
