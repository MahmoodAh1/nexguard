import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mutate = vi.fn();

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "a@b.c", role: "analyst" } }),
}));

vi.mock("@/lib/queries", () => ({
  useAlertFeedback: () => ({ data: [] }),
  useSubmitFeedback: () => ({ mutate, isPending: false, isError: false, error: null }),
}));

import { FeedbackControls } from "@/components/feedback-controls";

describe("FeedbackControls", () => {
  it("renders label options and submits the analyst verdict", () => {
    render(<FeedbackControls alertId="alert-1" />);
    expect(screen.getByText(/label this alert/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText("True Positive"));
    expect(mutate).toHaveBeenCalledWith({ alertId: "alert-1", label: "true_positive" });
  });
});
