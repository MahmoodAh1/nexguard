/** Runtime configuration derived from public env vars (with sane dev defaults). */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const config = {
  apiBaseUrl: API_URL,
  wsUrl: (path: "/ws/alerts" | "/ws/metrics", token: string): string => {
    const base = API_URL.replace(/^http/, "ws");
    return `${base}${path}?token=${encodeURIComponent(token)}`;
  },
} as const;
