"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight, Inbox } from "lucide-react";

import { SEVERITY_STYLES, SeverityBadge } from "@/components/severity";
import { Skeleton } from "@/components/ui/skeleton";
import type { Alert, AlertStatus } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

const STATUS_STYLES: Record<AlertStatus, string> = {
  new: "text-primary bg-primary/10 border-primary/20",
  triaged: "text-accent bg-accent/10 border-accent/20",
  investigating: "text-medium bg-medium/10 border-medium/20",
  resolved: "text-info bg-info/10 border-info/20",
  dismissed: "text-subtle bg-surface-2 border-border",
};

const COLS = "grid grid-cols-[110px_1fr_120px_120px_80px_92px_28px] items-center gap-3";

interface AlertsTableProps {
  alerts: Alert[];
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function AlertsTable({ alerts, isLoading, selectedId, onSelect }: AlertsTableProps) {
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[760px]">
        <div
          className={cn(
            COLS,
            "border-b border-border px-4 pb-2.5 text-[11px] font-medium uppercase tracking-wider text-subtle",
          )}
        >
          <span>Severity</span>
          <span>Session</span>
          <span>Anomaly score</span>
          <span>Status</span>
          <span className="text-right">Events</span>
          <span className="text-right">Detected</span>
          <span />
        </div>

        {isLoading ? (
          <LoadingRows />
        ) : alerts.length === 0 ? (
          <EmptyState />
        ) : (
          <ul>
            <AnimatePresence initial={false}>
              {alerts.map((alert) => (
                <motion.li
                  key={alert.id}
                  layout
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <button
                    type="button"
                    onClick={() => onSelect(alert.id)}
                    className={cn(
                      COLS,
                      "w-full border-b border-border/60 px-4 py-3 text-left transition-colors hover:bg-surface-2",
                      selectedId === alert.id && "bg-surface-2",
                    )}
                  >
                    <span>
                      <SeverityBadge severity={alert.severity} />
                    </span>
                    <span className="truncate font-mono text-sm text-foreground">
                      {alert.session_external_id}
                    </span>
                    <ScoreBar score={alert.score} severity={alert.severity} />
                    <span>
                      <span
                        className={cn(
                          "inline-flex rounded-md border px-2 py-0.5 text-xs font-medium capitalize",
                          STATUS_STYLES[alert.status],
                        )}
                      >
                        {alert.status}
                      </span>
                    </span>
                    <span className="text-right font-mono text-sm tabular-nums text-muted">
                      {alert.event_count}
                    </span>
                    <span className="text-right text-xs text-subtle">{timeAgo(alert.created_at)}</span>
                    <ChevronRight className="size-4 text-subtle" />
                  </button>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </div>
  );
}

function ScoreBar({ score, severity }: { score: number; severity: Alert["severity"] }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-2">
        <span
          className="block h-full rounded-full"
          style={{ width: `${Math.round(score * 100)}%`, backgroundColor: SEVERITY_STYLES[severity].chart }}
        />
      </span>
      <span className="font-mono text-sm tabular-nums text-foreground">{score.toFixed(2)}</span>
    </span>
  );
}

function LoadingRows() {
  return (
    <div className="divide-y divide-border/60">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className={cn(COLS, "px-4 py-3.5")}>
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-5 w-16" />
          <Skeleton className="ml-auto h-4 w-8" />
          <Skeleton className="ml-auto h-4 w-12" />
          <span />
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="grid size-12 place-items-center rounded-full bg-surface-2">
        <Inbox className="size-5 text-subtle" />
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">No alerts match this view</p>
        <p className="mt-1 text-xs text-muted">
          Seed the demo (<span className="font-mono text-subtle">nexguard seed</span>) or wait for
          live detections to arrive.
        </p>
      </div>
    </div>
  );
}
