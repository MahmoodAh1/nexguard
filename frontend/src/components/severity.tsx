import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/types";

interface SeverityStyle {
  label: string;
  text: string;
  bg: string;
  border: string;
  dot: string;
  chart: string;
}

export const SEVERITY_STYLES: Record<Severity, SeverityStyle> = {
  critical: {
    label: "Critical",
    text: "text-critical",
    bg: "bg-critical/12",
    border: "border-critical/30",
    dot: "bg-critical",
    chart: "#ff5c7a",
  },
  high: {
    label: "High",
    text: "text-high",
    bg: "bg-high/12",
    border: "border-high/30",
    dot: "bg-high",
    chart: "#ff8a4c",
  },
  medium: {
    label: "Medium",
    text: "text-medium",
    bg: "bg-medium/12",
    border: "border-medium/30",
    dot: "bg-medium",
    chart: "#fbbf24",
  },
  low: {
    label: "Low",
    text: "text-low",
    bg: "bg-low/12",
    border: "border-low/30",
    dot: "bg-low",
    chart: "#38bdf8",
  },
};

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const style = SEVERITY_STYLES[severity];
  return (
    <Badge className={cn(style.bg, style.border, style.text, "uppercase tracking-wide", className)}>
      <span className={cn("size-1.5 rounded-full", style.dot)} aria-hidden />
      {style.label}
    </Badge>
  );
}
