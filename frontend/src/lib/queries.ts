"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  Alert,
  AlertDetail,
  AnalyticsSummary,
  CalibrationSnapshot,
  FeedbackItem,
  FeedbackLabel,
  FeedbackSummary,
  Health,
  IncidentReport,
  RuntimeConfig,
  SessionDetail,
  SessionSummary,
  SystemMetrics,
  TemplateItem,
} from "@/lib/types";

export const queryKeys = {
  alerts: (params?: Record<string, string>) => ["alerts", params ?? {}] as const,
  alert: (id: string) => ["alert", id] as const,
  report: (alertId: string) => ["report", alertId] as const,
  feedback: (alertId: string) => ["feedback", alertId] as const,
  feedbackSummary: ["feedback-summary"] as const,
  calibrations: ["calibrations"] as const,
  sessions: ["sessions"] as const,
  session: (id: string) => ["session", id] as const,
  templates: ["templates"] as const,
  analytics: ["analytics"] as const,
  config: ["config"] as const,
  health: ["health"] as const,
  metrics: ["metrics"] as const,
};

export function useAlerts(params: { severity?: string; status?: string; limit?: number } = {}) {
  const { token } = useAuth();
  const search = new URLSearchParams();
  if (params.severity) search.set("severity", params.severity);
  if (params.status) search.set("status", params.status);
  if (params.limit) search.set("limit", String(params.limit));
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

// ── Feedback ──
export function useAlertFeedback(alertId: string | null) {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.feedback(alertId ?? ""),
    queryFn: () => apiFetch<FeedbackItem[]>(`/api/v1/alerts/${alertId}/feedback`, { token }),
    enabled: Boolean(token && alertId),
  });
}

export function useSubmitFeedback() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { alertId: string; label: FeedbackLabel; note?: string }) =>
      apiFetch<FeedbackItem>(`/api/v1/alerts/${input.alertId}/feedback`, {
        method: "POST",
        token,
        body: { label: input.label, note: input.note ?? null },
      }),
    onSuccess: (_data, input) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feedback(input.alertId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.feedbackSummary });
    },
  });
}

export function useFeedbackSummary() {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.feedbackSummary,
    queryFn: () => apiFetch<FeedbackSummary>("/api/v1/feedback/summary", { token }),
    enabled: Boolean(token),
  });
}

export function useCalibrations() {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.calibrations,
    queryFn: () => apiFetch<CalibrationSnapshot[]>("/api/v1/feedback/calibrations", { token }),
    enabled: Boolean(token),
  });
}

export function useRecalibrate() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<CalibrationSnapshot>("/api/v1/feedback/recalibrate", { method: "POST", token }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feedbackSummary });
      queryClient.invalidateQueries({ queryKey: queryKeys.calibrations });
      queryClient.invalidateQueries({ queryKey: queryKeys.config });
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

// ── Log Explorer ──
export function useSessions(limit = 50) {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.sessions,
    queryFn: () => apiFetch<SessionSummary[]>(`/api/v1/sessions?limit=${limit}`, { token }),
    enabled: Boolean(token),
  });
}

export function useSession(id: string | null) {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.session(id ?? ""),
    queryFn: () => apiFetch<SessionDetail>(`/api/v1/sessions/${id}`, { token }),
    enabled: Boolean(token && id),
  });
}

export function useTemplates() {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.templates,
    queryFn: () => apiFetch<TemplateItem[]>("/api/v1/templates", { token }),
    enabled: Boolean(token),
  });
}

// ── Analytics & config ──
export function useAnalytics() {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.analytics,
    queryFn: () => apiFetch<AnalyticsSummary>("/api/v1/analytics/summary", { token }),
    enabled: Boolean(token),
    refetchInterval: 15000,
  });
}

export function useConfig() {
  const { token } = useAuth();
  return useQuery({
    queryKey: queryKeys.config,
    queryFn: () => apiFetch<RuntimeConfig>("/api/v1/config", { token }),
    enabled: Boolean(token),
  });
}

export function useUpdateConfig() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Partial<Pick<RuntimeConfig, "seq_weight" | "stat_weight" | "threshold">>) =>
      apiFetch<RuntimeConfig>("/api/v1/config", { method: "PUT", token, body: input }),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.config, data);
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}
