"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  BadgeCheck,
  Boxes,
  Clock,
  Cpu,
  FlaskConical,
  ListChecks,
  Loader2,
  Server,
  ShieldAlert,
  ShieldX,
  Sparkles,
} from "lucide-react";

import { FeedbackControls } from "@/components/feedback-controls";
import { SeverityBadge } from "@/components/severity";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { useAlert, useGenerateReport, useReport } from "@/lib/queries";
import type { AlertDetail, IncidentReport, IncidentReportPayload } from "@/lib/types";
import { cn, formatTimestamp } from "@/lib/utils";

interface ReportDrawerProps {
  alertId: string | null;
  onOpenChange: (open: boolean) => void;
}

export function ReportDrawer({ alertId, onOpenChange }: ReportDrawerProps) {
  const alertQuery = useAlert(alertId);
  const reportQuery = useReport(alertId);
  const generate = useGenerateReport();
  const { user } = useAuth();
  const canTriage = user?.role === "analyst" || user?.role === "admin";

  const alert = alertQuery.data;

  return (
    <Sheet open={alertId !== null} onOpenChange={onOpenChange}>
      <SheetContent aria-describedby={undefined}>
        <SheetHeader>
          <div className="flex items-center gap-3 pr-8">
            {alert ? <SeverityBadge severity={alert.severity} /> : <Skeleton className="h-5 w-20" />}
            <SheetTitle className="font-mono">{alert?.session_external_id ?? "Alert"}</SheetTitle>
          </div>
          <SheetDescription>
            {alert
              ? `${alert.dataset.toUpperCase()} · anomaly score ${alert.score.toFixed(3)} · ${alert.event_count} events`
              : "Loading alert evidence…"}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          {alert && <FeedbackControls alertId={alert.id} />}
          {alert ? <EvidenceView alert={alert} /> : <EvidenceSkeleton />}

          <section className="space-y-3">
            <SectionTitle icon={Sparkles} title="AI Triage Report" />
            {reportQuery.isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : reportQuery.data ? (
              <ReportView report={reportQuery.data} />
            ) : (
              <div className="rounded-lg border border-dashed border-border bg-surface/50 p-5 text-center">
                <p className="text-sm text-muted">
                  No report yet. The local LLM drafts a structured, verified incident report.
                </p>
                {canTriage ? (
                  <Button
                    className="mt-4"
                    disabled={generate.isPending || !alertId}
                    onClick={() => alertId && generate.mutate(alertId)}
                  >
                    {generate.isPending ? (
                      <>
                        <Loader2 className="animate-spin" /> Generating…
                      </>
                    ) : (
                      <>
                        <Sparkles /> Generate report
                      </>
                    )}
                  </Button>
                ) : (
                  <p className="mt-3 text-xs text-subtle">Requires the analyst role.</p>
                )}
                {generate.isError && (
                  <p className="mt-3 text-xs text-critical">
                    {(generate.error as Error).message}
                  </p>
                )}
              </div>
            )}
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function EvidenceView({ alert }: { alert: AlertDetail }) {
  const { sequence, statistical, ensemble, provenance } = alert.evidence;
  return (
    <section className="space-y-3">
      <SectionTitle icon={ShieldAlert} title="Detection Evidence" />
      <div className="grid grid-cols-2 gap-3">
        <Metric label="Sequence (DeepLog)" value={sequence.anomaly_score.toFixed(2)} accent="high" />
        <Metric label="Statistical (iForest)" value={statistical.anomaly_score.toFixed(2)} accent="low" />
        <Metric label="Ensemble score" value={ensemble.final_score.toFixed(2)} accent="critical" />
        <Metric label="Threshold" value={ensemble.threshold.toFixed(2)} accent="muted" />
      </div>

      <Panel icon={Activity} title="Sequence model">
        <Row label="Perplexity" value={sequence.perplexity.toFixed(2)} />
        <Row label="Confidence" value={sequence.confidence.toFixed(2)} />
        <Row
          label="Predicted vs actual"
          value={`[${sequence.predicted_topk.join(", ")}] ≠ ${sequence.actual_event ?? "—"}`}
        />
        <Row
          label="Suspicious subsequence"
          value={sequence.suspicious_subsequence.length ? sequence.suspicious_subsequence.join(" → ") : "—"}
        />
      </Panel>

      {statistical.important_features.length > 0 && (
        <Panel icon={Cpu} title="Top statistical drivers">
          <ul className="space-y-1.5">
            {statistical.important_features.map((feature) => (
              <li key={feature.event_id} className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate font-mono text-muted">
                  #{feature.event_id} {feature.template ?? ""}
                </span>
                <span className="font-mono tabular-nums text-foreground">
                  +{feature.contribution.toFixed(3)}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel icon={Server} title="Provenance">
        <Row label="Dataset" value={provenance.dataset.toUpperCase()} />
        <Row label="Events" value={String(provenance.event_count)} />
        {provenance.started_at && <Row label="Started" value={formatTimestamp(provenance.started_at)} />}
        {provenance.ended_at && <Row label="Ended" value={formatTimestamp(provenance.ended_at)} />}
      </Panel>
    </section>
  );
}

function ReportView({ report }: { report: IncidentReport }) {
  if (!report.payload) {
    return <RejectionBanner reasons={report.rejected_reasons} model={report.model} />;
  }
  const p: IncidentReportPayload = report.payload;
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      {report.verified ? (
        <div className="flex items-center gap-2 rounded-md border border-info/30 bg-info/10 px-3 py-2 text-sm text-info">
          <BadgeCheck className="size-4" />
          Verified — every citation is grounded in real evidence.
        </div>
      ) : (
        <RejectionBanner reasons={report.rejected_reasons} model={report.model} />
      )}

      <p className="text-sm leading-relaxed text-foreground/90">{p.summary}</p>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <SeverityBadge severity={p.severity} />
        <span className="rounded-md border border-border bg-surface-2 px-2 py-0.5 text-muted">
          Confidence: {p.confidence}
        </span>
        <span className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-subtle">
          {report.model}
        </span>
      </div>

      {p.timeline.length > 0 && (
        <Panel icon={Clock} title="Timeline">
          <ol className="space-y-2">
            {p.timeline.map((entry, index) => (
              <li key={index} className="flex gap-3 text-sm">
                <span className="whitespace-nowrap font-mono text-xs text-subtle">
                  {formatTimestamp(entry.timestamp)}
                </span>
                <span className="text-muted">{entry.description}</span>
              </li>
            ))}
          </ol>
        </Panel>
      )}

      {p.affected_components.length > 0 && (
        <Panel icon={Boxes} title="Affected components">
          <div className="flex flex-wrap gap-1.5">
            {p.affected_components.map((component) => (
              <span
                key={component}
                className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-xs text-muted"
              >
                {component}
              </span>
            ))}
          </div>
        </Panel>
      )}

      {p.mitre_hypotheses.length > 0 && (
        <Panel icon={FlaskConical} title="MITRE ATT&CK">
          <ul className="space-y-2.5">
            {p.mitre_hypotheses.map((hypothesis) => (
              <li key={hypothesis.technique_id} className="text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-primary">{hypothesis.technique_id}</span>
                  <span className="text-foreground">{hypothesis.name}</span>
                  <span className="rounded border border-medium/40 bg-medium/10 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-medium">
                    Hypothesis
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-muted">{hypothesis.rationale}</p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <StepList icon={ListChecks} title="Recommended investigation" items={p.recommended_investigation_steps} />
      {p.recommended_containment_actions.length > 0 && (
        <StepList icon={ShieldAlert} title="Recommended containment" items={p.recommended_containment_actions} />
      )}
    </motion.div>
  );
}

function RejectionBanner({ reasons, model }: { reasons: string[]; model: string }) {
  return (
    <div className="rounded-md border border-critical/30 bg-critical/10 p-3">
      <div className="flex items-center gap-2 text-sm font-medium text-critical">
        <ShieldX className="size-4" />
        Report rejected by the verifier ({model})
      </div>
      <ul className="mt-2 space-y-1 text-xs text-critical/90">
        {reasons.map((reason, index) => (
          <li key={index}>• {reason}</li>
        ))}
      </ul>
    </div>
  );
}

/* — small presentational helpers — */

function SectionTitle({ icon: Icon, title }: { icon: typeof Activity; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 text-primary" />
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
    </div>
  );
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: "critical" | "high" | "low" | "muted";
}) {
  const color = {
    critical: "text-critical",
    high: "text-high",
    low: "text-low",
    muted: "text-muted",
  }[accent];
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <p className="text-[11px] uppercase tracking-wider text-subtle">{label}</p>
      <p className={cn("mt-1 font-mono text-xl font-semibold tabular-nums", color)}>{value}</p>
    </div>
  );
}

function Panel({ icon: Icon, title, children }: { icon: typeof Activity; title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-2.5 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-subtle">
        <Icon className="size-3.5" />
        {title}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-0.5 text-sm">
      <span className="text-muted">{label}</span>
      <span className="truncate text-right font-mono text-foreground">{value}</span>
    </div>
  );
}

function StepList({ icon, title, items }: { icon: typeof Activity; title: string; items: string[] }) {
  return (
    <Panel icon={icon} title={title}>
      <ol className="space-y-1.5">
        {items.map((item, index) => (
          <li key={index} className="flex gap-2 text-sm text-muted">
            <span className="font-mono text-xs text-subtle">{index + 1}.</span>
            {item}
          </li>
        ))}
      </ol>
    </Panel>
  );
}

function EvidenceSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-5 w-40" />
      <div className="grid grid-cols-2 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
      <Skeleton className="h-28 w-full" />
    </div>
  );
}
