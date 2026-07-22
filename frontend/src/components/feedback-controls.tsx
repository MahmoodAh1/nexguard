"use client";

import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useAlertFeedback, useSubmitFeedback } from "@/lib/queries";
import type { FeedbackLabel } from "@/lib/types";
import { cn } from "@/lib/utils";

const OPTIONS: Array<{ label: FeedbackLabel; text: string; active: string }> = [
  { label: "true_positive", text: "True Positive", active: "bg-info/15 text-info border-info/30" },
  {
    label: "false_positive",
    text: "False Positive",
    active: "bg-critical/15 text-critical border-critical/30",
  },
  { label: "benign", text: "Benign", active: "bg-surface-2 text-foreground border-border-strong" },
];

export function FeedbackControls({ alertId }: { alertId: string }) {
  const { user } = useAuth();
  const canLabel = user?.role === "analyst" || user?.role === "admin";
  const feedback = useAlertFeedback(alertId);
  const submit = useSubmitFeedback();
  const current = feedback.data?.[0]?.label ?? null;

  if (!canLabel) {
    return current ? (
      <p className="text-xs text-muted">
        Analyst verdict: <span className="text-foreground">{current.replace("_", " ")}</span>
      </p>
    ) : null;
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="mb-2.5 text-xs font-medium uppercase tracking-wider text-subtle">
        Investigate — label this alert
      </p>
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((option) => {
          const isCurrent = current === option.label;
          return (
            <Button
              key={option.label}
              variant="outline"
              size="sm"
              disabled={submit.isPending}
              onClick={() => submit.mutate({ alertId, label: option.label })}
              className={cn(isCurrent && option.active)}
            >
              {isCurrent && <Check className="size-3.5" />}
              {option.text}
            </Button>
          );
        })}
      </div>
      {submit.isError && (
        <p className="mt-2 text-xs text-critical">{(submit.error as Error).message}</p>
      )}
    </div>
  );
}
