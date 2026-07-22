"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { SEVERITY_STYLES } from "@/components/severity";
import type { Alert, Severity } from "@/lib/types";

const ORDER: Severity[] = ["critical", "high", "medium", "low"];

export function SeverityDonut({ alerts }: { alerts: Alert[] }) {
  const counts = ORDER.map((severity) => ({
    severity,
    label: SEVERITY_STYLES[severity].label,
    value: alerts.filter((a) => a.severity === severity).length,
    color: SEVERITY_STYLES[severity].chart,
  }));
  const total = alerts.length;
  const data = total === 0 ? [{ severity: "low" as Severity, label: "None", value: 1, color: "#222b3d" }] : counts;

  return (
    <div className="flex items-center gap-6">
      <div className="relative size-36 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              innerRadius={48}
              outerRadius={68}
              paddingAngle={total === 0 ? 0 : 3}
              stroke="none"
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
            >
              {data.map((entry) => (
                <Cell key={entry.severity} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-2xl font-semibold tabular-nums text-foreground">{total}</span>
          <span className="text-[10px] uppercase tracking-wider text-muted">Alerts</span>
        </div>
      </div>
      <ul className="flex flex-1 flex-col gap-2">
        {counts.map((entry) => (
          <li key={entry.severity} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-muted">
              <span className="size-2.5 rounded-sm" style={{ backgroundColor: entry.color }} aria-hidden />
              {entry.label}
            </span>
            <span className="font-mono tabular-nums text-foreground">{entry.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
