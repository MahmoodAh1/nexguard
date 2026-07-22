"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Activity, Bell, Cpu, Gauge, ShieldAlert } from "lucide-react";

import { AlertsTable } from "@/components/alerts-table";
import { LiveStatus } from "@/components/live-status";
import { ReportDrawer } from "@/components/report-drawer";
import { SeverityDonut } from "@/components/severity-donut";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { useAlerts, useHealth, useSystemMetrics } from "@/lib/queries";
import type { Severity } from "@/lib/types";
import { useLiveAlerts } from "@/lib/ws";
import { cn } from "@/lib/utils";

const FILTERS: Array<{ label: string; value: Severity | "all" }> = [
  { label: "All", value: "all" },
  { label: "Critical", value: "critical" },
  { label: "High", value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low", value: "low" },
];

export default function DashboardPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Severity | "all">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const alertsQuery = useAlerts(filter === "all" ? {} : { severity: filter });
  const unfilteredQuery = useAlerts({});
  const health = useHealth();
  const metrics = useSystemMetrics();

  const { status: liveStatus } = useLiveAlerts(token, () => {
    queryClient.invalidateQueries({ queryKey: ["alerts"] });
  });

  const allAlerts = unfilteredQuery.data ?? [];
  const criticalHigh = useMemo(
    () => allAlerts.filter((a) => a.severity === "critical" || a.severity === "high").length,
    [allAlerts],
  );
  const avgScore = useMemo(
    () => (allAlerts.length ? allAlerts.reduce((s, a) => s + a.score, 0) / allAlerts.length : 0),
    [allAlerts],
  );

  return (
    <div className="mx-auto max-w-[1400px] space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Executive Dashboard
          </h1>
          <p className="mt-0.5 text-sm text-muted">
            Real-time posture across the detection pipeline.
          </p>
        </div>
        <LiveStatus status={liveStatus} />
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Active Alerts" value={allAlerts.length} icon={Bell} accent="primary" />
        <StatCard
          label="Critical / High"
          value={criticalHigh}
          hint="require triage"
          icon={ShieldAlert}
          accent="critical"
        />
        <StatCard
          label="Avg Anomaly Score"
          value={avgScore.toFixed(2)}
          icon={Gauge}
          accent="high"
        />
        <StatCard
          label="CPU"
          value={metrics.data ? `${metrics.data.cpu_percent.toFixed(0)}%` : "—"}
          hint={metrics.data ? `${metrics.data.memory_percent.toFixed(0)}% memory` : undefined}
          icon={Activity}
          accent="info"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Alert Feed</CardTitle>
            <div className="flex items-center gap-1 rounded-md border border-border bg-surface p-0.5">
              {FILTERS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setFilter(option.value)}
                  className={cn(
                    "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                    filter === option.value
                      ? "bg-surface-2 text-foreground"
                      : "text-muted hover:text-foreground",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent className="px-0">
            <AlertsTable
              alerts={alertsQuery.data ?? []}
              isLoading={alertsQuery.isLoading}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Severity Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <SeverityDonut alerts={allAlerts} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Model &amp; System Health</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5">
              <HealthRow
                label="Detection models"
                value={health.data?.detectors_loaded ? "Online" : "Offline"}
                good={health.data?.detectors_loaded ?? false}
              />
              <HealthRow label="LLM provider" value={health.data?.llm_provider ?? "—"} good />
              <HealthRow label="Event bus" value={health.data?.event_bus ?? "—"} good />
              <HealthRow label="Environment" value={health.data?.environment ?? "—"} good />
              <div className="border-t border-border pt-2.5">
                <HealthRow
                  label="Process memory"
                  value={metrics.data ? `${metrics.data.process_rss_mb.toFixed(0)} MB` : "—"}
                  mono
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <ReportDrawer alertId={selectedId} onOpenChange={(open) => !open && setSelectedId(null)} />
    </div>
  );
}

function HealthRow({
  label,
  value,
  good,
  mono,
}: {
  label: string;
  value: string;
  good?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted">{label}</span>
      <span className="flex items-center gap-2">
        {good !== undefined && (
          <span className={cn("size-1.5 rounded-full", good ? "bg-info" : "bg-critical")} />
        )}
        <span className={cn("capitalize text-foreground", mono && "font-mono tabular-nums")}>
          {value}
        </span>
      </span>
    </div>
  );
}
