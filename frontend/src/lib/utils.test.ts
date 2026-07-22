import { describe, expect, it } from "vitest";

import { cn, formatTimestamp, timeAgo } from "@/lib/utils";

describe("cn", () => {
  it("joins class names and drops falsy values", () => {
    expect(cn("a", false, "b", undefined, "c")).toBe("a b c");
  });

  it("resolves conflicting tailwind utilities (last wins)", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});

describe("timeAgo", () => {
  it("formats recent times in seconds", () => {
    const iso = new Date(Date.now() - 5000).toISOString();
    expect(timeAgo(iso)).toMatch(/^\d+s ago$/);
  });

  it("formats minutes", () => {
    const iso = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(timeAgo(iso)).toBe("5m ago");
  });

  it("returns empty string for invalid input", () => {
    expect(timeAgo("not-a-date")).toBe("");
  });
});

describe("formatTimestamp", () => {
  it("returns a readable string for a valid ISO timestamp", () => {
    expect(formatTimestamp("2026-01-01T12:34:56+00:00")).not.toBe("");
  });

  it("echoes back an unparseable value", () => {
    expect(formatTimestamp("garbage")).toBe("garbage");
  });
});
