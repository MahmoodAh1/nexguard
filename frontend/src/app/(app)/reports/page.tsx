"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { FileText, Sparkles } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { ReportDrawer } from "@/components/report-drawer";
import { SeverityBadge } from "@/components/severity";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlerts } from "@/lib/queries";
import { timeAgo } from "@/lib/utils";

export default function IncidentReportsPage() {
  const query = useAlerts({ limit: 100 });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const alerts = useMemo(
    () => [...(query.data ?? [])].sort((a, b) => b.score - a.score),
    [query.data],
  );

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Incident Reports"
        description="AI-drafted, evidence-verified incident reports for suspicious sessions."
      />

      {query.isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-36 w-full" />
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <Card className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <div className="grid size-12 place-items-center rounded-full bg-surface-2">
            <FileText className="size-5 text-subtle" />
          </div>
          <p className="text-sm font-medium text-foreground">No incidents to report</p>
          <p className="text-xs text-muted">Alerts will appear here as detections arrive.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {alerts.map((alert, index) => (
            <motion.button
              key={alert.id}
              type="button"
              onClick={() => setSelectedId(alert.id)}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: Math.min(index * 0.02, 0.3) }}
              className="group text-left"
            >
              <Card className="h-full p-5 transition-colors hover:border-border-strong hover:bg-surface-2">
                <div className="flex items-center justify-between">
                  <SeverityBadge severity={alert.severity} />
                  <span className="text-xs text-subtle">{timeAgo(alert.created_at)}</span>
                </div>
                <p className="mt-3 truncate font-mono text-sm text-foreground">
                  {alert.session_external_id}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {alert.dataset.toUpperCase()} · {alert.event_count} events · score{" "}
                  <span className="font-mono text-foreground">{alert.score.toFixed(2)}</span>
                </p>
                <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-primary">
                  <Sparkles className="size-3.5" />
                  Open triage report
                </div>
              </Card>
            </motion.button>
          ))}
        </div>
      )}

      <ReportDrawer alertId={selectedId} onOpenChange={(open) => !open && setSelectedId(null)} />
    </div>
  );
}
