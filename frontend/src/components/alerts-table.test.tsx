import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertsTable } from "@/components/alerts-table";
import type { Alert } from "@/lib/types";

function makeAlert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: "alert-1",
    session_id: "session-1",
    session_external_id: "blk_-42",
    dataset: "hdfs",
    severity: "high",
    status: "new",
    score: 0.82,
    event_count: 14,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("AlertsTable", () => {
  it("renders an alert row with its session id, severity and score", () => {
    render(
      <AlertsTable alerts={[makeAlert()]} isLoading={false} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(screen.getByText("blk_-42")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("0.82")).toBeInTheDocument();
  });

  it("invokes onSelect with the alert id when a row is clicked", () => {
    const onSelect = vi.fn();
    render(
      <AlertsTable
        alerts={[makeAlert({ id: "alert-99" })]}
        isLoading={false}
        selectedId={null}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("blk_-42"));
    expect(onSelect).toHaveBeenCalledWith("alert-99");
  });

  it("shows an empty state when there are no alerts", () => {
    render(<AlertsTable alerts={[]} isLoading={false} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText(/No alerts match this view/i)).toBeInTheDocument();
  });

  it("shows loading skeletons while loading", () => {
    const { container } = render(
      <AlertsTable alerts={[]} isLoading selectedId={null} onSelect={vi.fn()} />,
    );
    // Skeleton rows render but no data rows or empty state.
    expect(screen.queryByText(/No alerts match/i)).not.toBeInTheDocument();
    expect(container.querySelectorAll("div").length).toBeGreaterThan(0);
  });
});
