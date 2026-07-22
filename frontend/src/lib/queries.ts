"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  Alert,
  AlertDetail,
  Health,
  IncidentReport,
  SystemMetrics,
} from "@/lib/types";

export const queryKeys = {
  alerts: (params?: Record<string, string>) => ["alerts", params ?? {}] as const,
  alert: (id: string) => ["alert", id] as const,
  report: (alertId: string) => ["report", alertId] as const,
  health: ["health"] as const,
  metrics: ["metrics"] as const,
};

export function useAlerts(params: { severity?: string } = {}) {
  const { token } = useAuth();
  const search = new URLSearchParams();
  if (params.severity) search.set("severity", params.severity);
  const qs = search.toString();
  return useQuery({
    queryKey: queryKeys.alerts(params as Record<string, string>),
    queryFn: () => apiFetch<Alert[]>(`/api/v1/alerts${qs ? `?${qs}` : ""}`, { token }),
    enabled: Boolean(token),
    refetchInterval: 20000,
  });
}

export function useAlert(id: string | null) {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.alert(id ?? ""),
    queryFn: () => apiFetch<AlertDetail>(`/api/v1/alerts/${id}`, { token }),
    enabled: Boolean(token && id),
  });
}

export function useReport(alertId: string | null) {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.report(alertId ?? ""),
    queryFn: async () => {
      try {
        return await apiFetch<IncidentReport>(`/api/v1/alerts/${alertId}/report`, { token });
      } catch {
        return null; // no report generated yet
      }
    },
    enabled: Boolean(token && alertId),
  });
}

export function useGenerateReport() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) =>
      apiFetch<IncidentReport>(`/api/v1/alerts/${alertId}/report`, { method: "POST", token }),
    onSuccess: (report) => {
      queryClient.setQueryData(queryKeys.report(report.alert_id), report);
    },
  });
}

export function useHealth() {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => apiFetch<Health>("/health", { token }),
    enabled: Boolean(token),
    refetchInterval: 30000,
  });
}

export function useSystemMetrics() {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.metrics,
    queryFn: () => apiFetch<SystemMetrics>("/api/v1/metrics/system", { token }),
    enabled: Boolean(token),
    refetchInterval: 5000,
  });
}
