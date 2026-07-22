"use client";

import { RefreshCw } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { useCalibrations, useFeedbackSummary, useRecalibrate } from "@/lib/queries";
import type { CalibrationSnapshot } from "@/lib/types";
import { formatTimestamp } from "@/lib/utils";

const LABELS: Array<{ key: string; text: string; className: string }> = [
  { key: "true_positive", text: "True Positive", className: "text-info" },
  { key: "false_positive", text: "False Positive", className: "text-critical" },
  { key: "benign", text: "Benign", className: "text-muted" },
  { key: "unknown", text: "Unknown", className: "text-subtle" },
];

export default function FeedbackCenterPage() {
  const { user } = useAuth();
  const summary = useFeedbackSummary();
  const calibrations = useCalibrations();
  const recalibrate = useRecalibrate();
  const canRecalibrate = user?.role === "admin";
  const latest = summary.data?.latest_calibration;

  return (
    <div className="mx-auto max-w-[1400px] space-y-6">
      <PageHeader
        title="Feedback Center"
        description="Analyst verdicts and their measurable effect on detection quality."
      >
        {canRecalibrate && (
          <Button
            size="sm"
            disabled={recalibrate.isPending || (summary.data?.total ?? 0) === 0}
            onClick={() => recalibrate.mutate()}
          >
            <RefreshCw className={recalibrate.isPending ? "animate-spin" : ""} />
            {recalibrate.isPending ? "Recalibrating…" : "Recalibrate"}
          </Button>
        )}
      </PageHeader>

      {recalibrate.isError && (
        <p className="text-sm text-critical">{(recalibrate.error as Error).message}</p>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {LABELS.map((label) => (
          <Card key={label.key} className="p-5">
            <p className="text-xs font-medium uppercase tracking-wider text-muted">{label.text}</p>
            <p className={`mt-2 font-mono text-3xl font-semibold ${label.className}`}>
              {summary.data?.counts[label.key] ?? 0}
            </p>
          </Card>
        ))}
      </div>

      {latest && (
        <Card>
          <CardHeader>
            <CardTitle>Latest Recalibration Impact</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <ImpactMetric label="Precision" before={latest.precision_before} after={latest.precision_after} />
            <ImpactMetric label="Recall" before={latest.recall_before} after={latest.recall_after} />
            <Stat label="Threshold" value={latest.threshold.toFixed(2)} />
            <Stat label="Feedback used" value={String(latest.feedback_count)} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Recalibration History</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto px-0">
          <div className="min-w-[720px]">
            <div className="grid grid-cols-[1fr_repeat(5,110px)] gap-3 border-b border-border px-4 pb-2 text-[11px] uppercase tracking-wider text-subtle">
              <span>When</span>
              <span className="text-right">Feedback</span>
              <span className="text-right">Threshold</span>
              <span className="text-right">Prec →</span>
              <span className="text-right">Recall →</span>
              <span className="text-right">ΔF-ish</span>
            </div>
            {calibrations.isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            ) : (calibrations.data ?? []).length === 0 ? (
              <p className="px-4 py-10 text-center text-sm text-muted">
                No recalibrations yet. Label alerts, then recalibrate.
              </p>
            ) : (
              (calibrations.data ?? []).map((snap) => <HistoryRow key={snap.id} snap={snap} />)
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function HistoryRow({ snap }: { snap: CalibrationSnapshot }) {
  const precisionDelta = snap.precision_after - snap.precision_before;
  return (
    <div className="grid grid-cols-[1fr_repeat(5,110px)] gap-3 border-b border-border/60 px-4 py-2.5 text-sm">
      <span className="text-xs text-muted">{formatTimestamp(snap.created_at)}</span>
      <span className="text-right font-mono text-foreground">{snap.feedback_count}</span>
      <span className="text-right font-mono text-foreground">{snap.threshold.toFixed(2)}</span>
      <span className="text-right font-mono text-foreground">
        {snap.precision_before.toFixed(2)}→{snap.precision_after.toFixed(2)}
      </span>
      <span className="text-right font-mono text-foreground">
        {snap.recall_before.toFixed(2)}→{snap.recall_after.toFixed(2)}
      </span>
      <span className={`text-right font-mono ${precisionDelta >= 0 ? "text-info" : "text-critical"}`}>
        {precisionDelta >= 0 ? "+" : ""}
        {precisionDelta.toFixed(2)}
      </span>
    </div>
  );
}

function ImpactMetric({
  label,
  before,
  after,
}: {
  label: string;
  before: number;
  after: number;
}) {
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="text-[11px] uppercase tracking-wider text-subtle">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold text-foreground">{value}</p>
    </div>
  );
}
