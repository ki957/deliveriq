import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NotBuilt } from "./not-built";
import { DeniedState, EmptyState, ErrorState, LoadingState } from "./states";
import { StatusBadge } from "./status-badge";
import { ImageUnavailable, Wordmark } from "./wordmark";

describe("shared UI", () => {
  it("status badges carry text and an icon, not colour alone", () => {
    const { container } = render(<StatusBadge tone="danger" label="Delayed" />);
    expect(screen.getByText("Delayed")).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
    expect(container.firstElementChild).toHaveAttribute("data-tone", "danger");
  });

  it("screen states use status and alert roles", () => {
    render(
      <>
        <LoadingState />
        <EmptyState title="No orders yet" />
        <ErrorState />
        <DeniedState />
      </>,
    );
    expect(screen.getAllByRole("status")).toHaveLength(2);
    expect(screen.getAllByRole("alert")).toHaveLength(2);
  });

  it("placeholders are labelled as placeholders", () => {
    render(
      <>
        <Wordmark />
        <ImageUnavailable />
        <NotBuilt title="Live Orders" task={8} />
        <NotBuilt title="Support" />
      </>,
    );
    expect(screen.getByText("Placeholder logo")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Image unavailable" })).toBeInTheDocument();
    expect(screen.getByText(/planned in Task 8/)).toBeInTheDocument();
    expect(screen.getByText(/planned in a later task/)).toBeInTheDocument();
  });
});
