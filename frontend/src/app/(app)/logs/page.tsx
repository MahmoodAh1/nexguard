"use client";

import { useState } from "react";
import { Boxes, FileCode2, Hash } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession, useSessions, useTemplates } from "@/lib/queries";
import { cn, formatTimestamp } from "@/lib/utils";

type Tab = "sessions" | "templates";

export default function LogExplorerPage() {
  const [tab, setTab] = useState<Tab>("sessions");

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Log Explorer"
        description="Parsed sessions, their event sequences, and the mined templates."
      >
        <div className="flex items-center gap-0.5 rounded-md border border-border bg-surface p-0.5">
          {(["sessions", "templates"] as Tab[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setTab(option)}
              className={cn(
                "rounded px-3 py-1 text-xs font-medium capitalize transition-colors",
                tab === option ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground",
              )}
            >
              {option}
            </button>
          ))}
        </div>
      </PageHeader>

      {tab === "sessions" ? <SessionsView /> : <TemplatesView />}
    </div>
  );
}

function SessionsView() {
  const sessions = useSessions(100);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const activeId = selectedId ?? sessions.data?.[0]?.id ?? null;
  const detail = useSession(activeId);
  const events = detail.data?.events ?? [];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
      <Card className="max-h-[70vh] overflow-y-auto">
        <CardHeader>
          <CardTitle>Sessions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 px-2 pb-2">
          {sessions.isLoading
            ? Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))
            : (sessions.data ?? []).map((session) => (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => setSelectedId(session.id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-left transition-colors hover:bg-surface-2",
                    activeId === session.id && "bg-surface-2",
                  )}
                >
                  <span className="truncate font-mono text-xs text-foreground">
                    {session.external_id}
                  </span>
                  <span className="flex items-center gap-1.5 text-[10px] text-subtle">
                    {session.label === true && (
                      <span className="rounded bg-critical/15 px-1 py-px text-critical">anom</span>
                    )}
                    {session.event_count} ev
                  </span>
                </button>
              ))}
        </CardContent>
      </Card>

      <Card className="max-h-[70vh] overflow-hidden">
        <CardHeader>
          <CardTitle>Event Sequence</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto px-0">
          <div className="min-w-[640px]">
            <div className="grid grid-cols-[56px_72px_1fr_150px] gap-3 border-b border-border px-4 pb-2 text-[11px] uppercase tracking-wider text-subtle">
              <span>Line</span>
              <span>Event</span>
              <span>Raw</span>
              <span className="text-right">Timestamp</span>
            </div>
            {events.length === 0 ? (
              <p className="px-4 py-10 text-center text-sm text-muted">
                Select a session to inspect its parsed events.
              </p>
            ) : (
              events.map((event) => (
                <div
                  key={event.line_no}
                  className="grid grid-cols-[56px_72px_1fr_150px] gap-3 border-b border-border/60 px-4 py-2 text-sm"
                >
                  <span className="font-mono text-subtle">{event.line_no}</span>
                  <span className="font-mono text-primary">#{event.event_id}</span>
                  <span className="truncate font-mono text-xs text-muted" title={event.raw}>
                    {event.raw}
                  </span>
                  <span className="text-right text-xs text-subtle">
                    {event.timestamp ? formatTimestamp(event.timestamp) : "—"}
                  </span>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function TemplatesView() {
  const templates = useTemplates();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCode2 className="size-4 text-primary" /> Mined Templates
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto px-0">
        <div className="min-w-[640px]">
          <div className="grid grid-cols-[72px_1fr_110px] gap-3 border-b border-border px-4 pb-2 text-[11px] uppercase tracking-wider text-subtle">
            <span>Event</span>
            <span>Template</span>
            <span className="text-right">Occurrences</span>
          </div>
          {templates.isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-6 w-full" />
              ))}
            </div>
          ) : (
            (templates.data ?? []).map((template) => (
              <div
                key={template.event_id}
                className="grid grid-cols-[72px_1fr_110px] gap-3 border-b border-border/60 px-4 py-2.5 text-sm"
              >
                <span className="flex items-center gap-1 font-mono text-primary">
                  <Hash className="size-3" />
                  {template.event_id}
                </span>
                <span className="truncate font-mono text-xs text-foreground" title={template.template}>
                  {template.template}
                </span>
                <span className="flex items-center justify-end gap-1.5 font-mono text-muted">
                  <Boxes className="size-3 text-subtle" />
                  {template.occurrences}
                </span>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
