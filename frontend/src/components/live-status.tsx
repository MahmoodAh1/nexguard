import { cn } from "@/lib/utils";
import type { LiveStatus as Status } from "@/lib/ws";

const STATUS = {
  live: { label: "Live", dot: "bg-info", text: "text-info", pulse: true },
  connecting: { label: "Connecting", dot: "bg-medium", text: "text-medium", pulse: true },
  offline: { label: "Offline", dot: "bg-subtle", text: "text-subtle", pulse: false },
} as const;

export function LiveStatus({ status }: { status: Status }) {
  const s = STATUS[status];
  return (
    <div
      className="flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1"
      role="status"
      aria-live="polite"
    >
      <span className="relative flex size-2">
        {s.pulse && (
          <span
            className={cn("absolute inline-flex size-full rounded-full opacity-60", s.dot)}
            style={{ animation: "nx-pulse 1.6s ease-in-out infinite" }}
            aria-hidden
          />
        )}
        <span className={cn("relative inline-flex size-2 rounded-full", s.dot)} aria-hidden />
      </span>
      <span className={cn("text-xs font-medium", s.text)}>{s.label}</span>
    </div>
  );
}
