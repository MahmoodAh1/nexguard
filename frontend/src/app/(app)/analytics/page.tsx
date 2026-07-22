"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Cpu, Gauge, ShieldCheck } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { SEVERITY_STYLES } from "@/components/severity";
import { StatCard } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { useAnalytics, useConfig, useUpdateConfig } from "@/lib/queries";
import type { Severity } from "@/lib/types";

const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low"];

export default function DetectionAnalyticsPage() {
  const analytics = useAnalytics();
  const data = analytics.data;

  return (
    <div className="mx-auto max-w-[1400px] space-y-6">
      <PageHeader
        title="Detection Analytics"
        description="Alert distribution, score spectrum, and the live detection operating point."
      />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Total Alerts" value={data?.total_alerts ?? "—"} icon={Activity} accent="primary" />
        <StatCard
          label="Detection Models"
          value={data?.detectors_loaded ? "Online" : "Offline"}
          icon={Cpu}
          accent={data?.detectors_loaded ? "info" : "high"}
        />
        <StatCard
          label="Threshold"
          value={data ? data.threshold.toFixed(2) : "—"}
          icon={Gauge}
          accent="high"
        />
        <StatCard
          label="Weights (seq/stat)"
          value={data ? `${data.seq_weight.toFixed(1)}/${data.stat_weight.toFixed(1)}` : "—"}
          icon={ShieldCheck}
          accent="muted"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Anomaly Score Spectrum</CardTitle>
          </CardHeader>
          <CardContent>
            {analytics.isLoading || !data ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <Histogram buckets={data.score_histogram} threshold={data.threshold} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Severity Mix</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-1">
            {SEV_ORDER.map((sev) => {
              const count = data?.by_severity[sev] ?? 0;
              const total = data?.total_alerts || 1;
              return (
                <div key={sev}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="capitalize text-muted">{sev}</span>
                    <span className="font-mono text-foreground">{count}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${(count / total) * 100}%`,
                        backgroundColor: SEVERITY_STYLES[sev].chart,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ThresholdTuner />
        {data?.latest_calibration && <CalibrationCard snapshot={data.latest_calibration} />}
      </div>
    </div>
  );
}

function Histogram({ buckets, threshold }: { buckets: { lower: number; count: number }[]; threshold: number }) {
  const chartData = buckets.map((b) => ({ label: b.lower.toFixed(1), count: b.count, lower: b.lower }));
  return (
    <ResponsiveContainer width="100%" height={224}>
      <BarChart data={chartData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <XAxis dataKey="label" stroke="#5b6678" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke="#5b6678" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
          contentStyle={{
            background: "#1a2130",
            border: "1px solid #2f3a4f",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: "#97a3b6" }}
        />
        <Bar dataKey="count" radius={[3, 3, 0, 0]}>
          {chartData.map((entry) => (
            <Cell key={entry.label} fill={entry.lower >= threshold ? "#ff5c7a" : "#4f8cff"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function ThresholdTuner() {
  const { user } = useAuth();
  const config = useConfig();
  const update = useUpdateConfig();
  const canTune = user?.role === "admin";
  const [value, setValue] = useState(0.5);

  useEffect(() => {
    if (config.data) setValue(config.data.threshold);
  }, [config.data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Threshold Tuning</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-baseline justify-between">
          <span className="text-sm text-muted">Decision threshold</span>
          <span className="font-mono text-2xl font-semibold tabular-nums text-foreground">
            {value.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={value}
          disabled={!canTune}
          onChange={(e) => setValue(Number(e.target.value))}
          className="w-full accent-primary disabled:opacity-50"
        />
        {canTune ? (
          <Button
            size="sm"
            disabled={update.isPending || value === config.data?.threshold}
            onClick={() => update.mutate({ threshold: value })}
          >
            {update.isPending ? "Applying…" : "Apply threshold"}
          </Button>
        ) : (
          <p className="text-xs text-subtle">Threshold tuning requires the admin role.</p>
        )}
      </CardContent>
    </Card>
  );
}

function CalibrationCard({
  snapshot,
}: {
  snapshot: { precision_before: number; recall_before: number; precision_after: number; recall_after: number };
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Latest Recalibration</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-4">
        <Metric label="Precision" before={snapshot.precision_before} after={snapshot.precision_after} />
        <Metric label="Recall" before={snapshot.recall_before} after={snapshot.recall_after} />
      </CardContent>
    </Card>
  );
}

function Metric({ label, before, after }: { label: string; before: number; after: number }) {
  const delta = after - before;
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="text-[11px] uppercase tracking-wider text-subtle">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold text-foreground">{after.toFixed(2)}</p>
      <p className="mt-0.5 text-xs text-muted">
        from {before.toFixed(2)}{" "}
        <span className={delta >= 0 ? "text-info" : "text-critical"}>
          ({delta >= 0 ? "+" : ""}
          {delta.toFixed(2)})
        </span>
      </p>
    </div>
  );
}
