"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { AlertsTable } from "@/components/alerts-table";
import { PageHeader } from "@/components/page-header";
import { ReportDrawer } from "@/components/report-drawer";
import { Card, CardContent } from "@/components/ui/card";
import { useAlerts } from "@/lib/queries";
import type { Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

const SEVERITIES: Array<Severity | "all"> = ["all", "critical", "high", "medium", "low"];
const STATUSES = ["all", "new", "triaged", "investigating", "resolved", "dismissed"] as const;

export default function AlertExplorerPage() {
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const query = useAlerts({
    severity: severity === "all" ? undefined : severity,
    status: status === "all" ? undefined : status,
    limit: 200,
  });

  const alerts = useMemo(() => {
    const rows = query.data ?? [];
    const term = search.trim().toLowerCase();
    return term ? rows.filter((a) => a.session_external_id.toLowerCase().includes(term)) : rows;
  }, [query.data, search]);

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Alert Explorer"
        description="Search, filter, and investigate detections across the fleet."
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
          <div className="relative min-w-[220px] flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by session / block id…"
              className="h-9 w-full rounded-md border border-border bg-surface pl-9 pr-3 text-sm text-foreground placeholder:text-subtle focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
          </div>
          <Segmented
            options={SEVERITIES}
            value={severity}
            onChange={(v) => setSeverity(v as Severity | "all")}
          />
          <Segmented
            options={STATUSES}
            value={status}
            onChange={(v) => setStatus(v as (typeof STATUSES)[number])}
          />
        </div>
        <CardContent className="px-0 pt-0">
          <div className="flex items-center justify-between px-4 py-2 text-xs text-subtle">
            <span>{alerts.length} alerts</span>
          </div>
          <AlertsTable
            alerts={alerts}
            isLoading={query.isLoading}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </CardContent>
      </Card>

      <ReportDrawer alertId={selectedId} onOpenChange={(open) => !open && setSelectedId(null)} />
    </div>
  );
}

function Segmented({
  options,
  value,
  onChange,
}: {
  options: readonly string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-0.5 rounded-md border border-border bg-surface p-0.5">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={cn(
            "rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors",
            value === option ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
