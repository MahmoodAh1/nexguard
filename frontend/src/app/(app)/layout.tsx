"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Bell,
  FileSearch,
  LayoutDashboard,
  Loader2,
  LogOut,
  MessageSquare,
  Radio,
  ScrollText,
  Settings,
  ShieldCheck,
} from "lucide-react";

import { Logo } from "@/components/logo";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Executive Dashboard", icon: LayoutDashboard },
  { href: "/alerts", label: "Alert Explorer", icon: Bell },
  { href: "/reports", label: "Incident Reports", icon: FileSearch },
  { href: "/logs", label: "Log Explorer", icon: ScrollText },
  { href: "/analytics", label: "Detection Analytics", icon: BarChart3 },
  { href: "/monitoring", label: "Live Monitoring", icon: Radio },
  { href: "/feedback", label: "Feedback Center", icon: MessageSquare },
  { href: "/config", label: "Configuration", icon: Settings },
] as const;

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { status, user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loader2 className="size-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-border bg-surface/60 backdrop-blur-md lg:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <Logo className="size-7" />
          <div className="leading-tight">
            <p className="text-sm font-semibold tracking-tight text-foreground">NexGuard</p>
            <p className="text-[10px] uppercase tracking-widest text-subtle">SecOps Platform</p>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-surface-2 font-medium text-foreground"
                    : "text-muted hover:bg-surface-2 hover:text-foreground",
                )}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
                )}
                <item.icon className="size-4 shrink-0" strokeWidth={1.75} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border p-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-2">
            <div className="grid size-8 place-items-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
              {user?.email?.[0]?.toUpperCase() ?? "?"}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-foreground">{user?.email}</p>
              <p className="text-[10px] uppercase tracking-wide text-subtle">{user?.role}</p>
            </div>
            <button
              type="button"
              onClick={logout}
              aria-label="Sign out"
              className="rounded-md p-1.5 text-subtle transition-colors hover:bg-surface-2 hover:text-critical"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg/80 px-5 backdrop-blur-md lg:px-8">
          <Logo className="size-6 lg:hidden" />
          <div className="flex items-center gap-2 text-sm text-muted">
            <ShieldCheck className="size-4 text-primary" />
            <span className="font-medium text-foreground">Security Operations</span>
          </div>
        </header>
        <main className="flex-1 px-5 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
