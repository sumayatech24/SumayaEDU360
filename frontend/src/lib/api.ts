import axios from "axios";

const baseURL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://127.0.0.1:8001";

export const api = axios.create({ baseURL: `${baseURL}/api/v1` });
export const publicApi = axios.create({ baseURL: `${baseURL}/api/v1` });

const TOKEN_KEY = "eduos_token";

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (
      err?.response?.status === 401 &&
      !location.pathname.startsWith("/login") &&
      !location.pathname.startsWith("/apply/")
    ) {
      setToken(null);
      location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export function apiError(err: unknown): string {
  const e = err as { response?: { data?: { detail?: unknown } } };
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d: any) => d.msg || JSON.stringify(d)).join(", ");
  return "Something went wrong";
}
