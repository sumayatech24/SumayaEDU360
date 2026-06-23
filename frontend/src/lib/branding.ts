import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface Branding {
  institution_name: string;
  logo_url: string;
  tagline: string;
  primary_color: string;
}

const FALLBACK: Branding = {
  institution_name: "SumayaEDU360",
  logo_url: "",
  tagline: "AI EduOS",
  primary_color: "#2563eb",
};

/** Tenant branding (logo, name, theme) — public endpoint, cached for the session. */
export function useBranding(): Branding {
  const { data } = useQuery({
    queryKey: ["branding"],
    queryFn: async () => (await api.get<Branding>("/branding")).data,
    staleTime: Infinity,
  });
  return data ?? FALLBACK;
}
