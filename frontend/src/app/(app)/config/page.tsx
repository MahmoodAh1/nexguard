"use client";

import { useEffect, useState } from "react";
import { Cpu, Save, Server, SlidersHorizontal } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { useConfig, useHealth, useUpdateConfig } from "@/lib/queries";

interface Form {
  seq_weight: number;
  stat_weight: number;
  threshold: number;
}

export default function ConfigurationPage() {
  const { user } = useAuth();
  const config = useConfig();
  const health = useHealth();
  const update = useUpdateConfig();
  const canEdit = user?.role === "admin";
  const [form, setForm] = useState<Form>({ seq_weight: 0.6, stat_weight: 0.4, threshold: 0.5 });

  useEffect(() => {
    if (config.data) {
      setForm({
        seq_weight: config.data.seq_weight,
        stat_weight: config.data.stat_weight,
        threshold: config.data.threshold,
      });
    }
  }, [config.data]);

  const dirty =
    config.data != null &&
    (form.seq_weight !== config.data.seq_weight ||
      form.stat_weight !== config.data.stat_weight ||
      form.threshold !== config.data.threshold);

  return (
    <div className="mx-auto max-w-[1000px] space-y-6">
      <PageHeader
        title="Configuration"
        description="Detection operating point, models, and system settings."
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SlidersHorizontal className="size-4 text-primary" /> Detection Operating Point
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <Slider
            label="Sequence weight"
            value={form.seq_weight}
            disabled={!canEdit}
            onChange={(v) => setForm((f) => ({ ...f, seq_weight: v }))}
          />
          <Slider
            label="Statistical weight"
            value={form.stat_weight}
            disabled={!canEdit}
            onChange={(v) => setForm((f) => ({ ...f, stat_weight: v }))}
          />
          <Slider
            label="Alert threshold"
            value={form.threshold}
            disabled={!canEdit}
            onChange={(v) => setForm((f) => ({ ...f, threshold: v }))}
          />
          {canEdit ? (
            <Button size="sm" disabled={!dirty || update.isPending} onClick={() => update.mutate(form)}>
              <Save />
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          ) : (
            <p className="text-xs text-subtle">Editing the operating point requires the admin role.</p>
          )}
          {update.isError && (
            <p className="text-xs text-critical">{(update.error as Error).message}</p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="size-4 text-primary" /> Models
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            <Row label="Detectors" value={config.data?.detectors_loaded ? "Loaded" : "Not loaded"} good={config.data?.detectors_loaded} />
            <Row label="LLM provider" value={config.data?.llm_provider ?? "—"} />
            <Row label="Report model" value={config.data?.model_name ?? "—"} mono />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="size-4 text-primary" /> System
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            <Row label="Environment" value={health.data?.environment ?? "—"} />
            <Row label="Version" value={health.data?.version ?? "—"} mono />
            <Row label="Event bus" value={health.data?.event_bus ?? "—"} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Slider({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-sm text-muted">{label}</span>
        <span className="font-mono text-sm font-semibold text-foreground">{value.toFixed(2)}</span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-primary disabled:opacity-50"
      />
    </div>
  );
}

function Row({
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
          <span className={`size-1.5 rounded-full ${good ? "bg-info" : "bg-high"}`} />
        )}
        <span className={mono ? "font-mono text-foreground" : "capitalize text-foreground"}>
          {value}
        </span>
      </span>
    </div>
  );
}
