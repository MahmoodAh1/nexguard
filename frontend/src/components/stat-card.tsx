import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  accent?: "primary" | "critical" | "high" | "info" | "muted";
}

const ACCENTS = {
  primary: "text-primary bg-primary/10",
  critical: "text-critical bg-critical/10",
  high: "text-high bg-high/10",
  info: "text-info bg-info/10",
  muted: "text-muted bg-surface-2",
} as const;

export function StatCard({ label, value, hint, icon: Icon, accent = "primary" }: StatCardProps) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-muted">{label}</p>
          <p className="mt-2 font-mono text-3xl font-semibold tabular-nums text-foreground">
            {value}
          </p>
          {hint && <p className="mt-1 text-xs text-subtle">{hint}</p>}
        </div>
        <div className={cn("grid size-9 place-items-center rounded-md", ACCENTS[accent])}>
          <Icon className="size-5" strokeWidth={1.75} />
        </div>
      </div>
    </Card>
  );
}
