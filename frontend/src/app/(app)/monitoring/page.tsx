"use client";

import { useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { Activity, Bell, Cpu, MemoryStick } from "lucide-react";

import { LiveStatus } from "@/components/live-status";
import { PageHeader } from "@/components/page-header";
import { SeverityBadge } from "@/components/severity";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import type { AlertCreatedEvent, MetricsTick } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useLiveAlerts, useLiveMetrics } from "@/lib/ws";

const WINDOW = 40;

export default function LiveMonitoringPage() {
  const { token } = useAuth();
  const [ticks, setTicks] = useState<MetricsTick[]>([]);
  const [events, setEvents] = useState<AlertCreatedEvent[]>([]);

  const { status } = useLiveMetrics(token, (tick) =>
    setTicks((prev) => [...prev.slice(-(WINDOW - 1)), tick]),
  );
  useLiveAlerts(token, (event) => setEvents((prev) => [event, ...prev].slice(0, 25)));

  const latest = ticks[ticks.length - 1];
  const chartData = ticks.map((t, i) => ({
    i,
    cpu: t.cpu_percent,
    memory: t.memory_percent,
  }));

  return (
    <div className="mx-auto max-w-[1400px] space-y-6">
      <PageHeader title="Live Monitoring" description="Real-time platform health and event stream.">
        <LiveStatus status={status} />
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label="CPU"
          value={latest ? `${latest.cpu_percent.toFixed(0)}%` : "—"}
          icon={Cpu}
          accent="primary"
        />
        <StatCard
          label="Memory"
          value={latest ? `${latest.memory_percent.toFixed(0)}%` : "—"}
          icon={MemoryStick}
          accent="info"
        />
        <StatCard
          label="Process RSS"
          value={latest ? `${latest.process_rss_mb.toFixed(0)} MB` : "—"}
          icon={Activity}
          accent="muted"
        />
        <StatCard
          label="Active Alerts"
          value={latest?.active_alerts ?? "—"}
          icon={Bell}
          accent="high"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Resource Utilization</CardTitle>
          </CardHeader>
          <CardContent>
            {chartData.length === 0 ? (
              <div className="flex h-48 items-center justify-center text-sm text-muted">
                Waiting for the first metrics tick…
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={192}>
                <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
                  <defs>
                    <linearGradient id="cpu" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#4f8cff" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#4f8cff" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="mem" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <YAxis
                    stroke="#5b6678"
                    fontSize={11}
                    domain={[0, 100]}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#1a2130",
                      border: "1px solid #2f3a4f",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelFormatter={() => ""}
                  />
                  <Area type="monotone" dataKey="cpu" stroke="#4f8cff" fill="url(#cpu)" strokeWidth={2} isAnimationActive={false} />
                  <Area type="monotone" dataKey="memory" stroke="#22d3ee" fill="url(#mem)" strokeWidth={2} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}
            <div className="mt-2 flex gap-4 text-xs text-muted">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-primary" /> CPU %
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-accent" /> Memory %
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="max-h-[420px] overflow-hidden">
          <CardHeader>
            <CardTitle>Event Stream</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 overflow-y-auto px-4">
            {events.length === 0 ? (
              <p className="py-8 text-center text-xs text-muted">
                Live <span className="font-mono">alert.created</span> events appear here.
              </p>
            ) : (
              events.map((event) => (
                <div
                  key={event.event_id}
                  className="flex items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={event.severity} />
                    <span className="truncate font-mono text-xs text-foreground">
                      {event.session_external_id}
                    </span>
                  </div>
                  <span className="text-[10px] text-subtle">{timeAgo(event.occurred_at)}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
