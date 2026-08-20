import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

function renderDialog(overrides: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) {
  const onClose = vi.fn();
  const onConfirm = vi.fn();
  const props = {
    isOpen: true,
    onClose,
    onConfirm,
    title: "Delete Repository",
    message: `Are you sure you want to delete "acme-widgets"?`,
    description: "This will permanently remove the repository, its analysis data, and associated workspace data. This action cannot be undone.",
    confirmLabel: "Delete",
    loadingLabel: "Deleting...",
    isLoading: false,
    error: "",
    variant: "danger" as const,
    ...overrides,
  };
  render(<ConfirmDialog {...props} />);
  return { onClose, onConfirm };
}

describe("ConfirmDialog", () => {
  it("renders as an accessible in-app dialog, never a native confirm()", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    renderDialog();

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("Delete Repository")).toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("shows the actual repository name dynamically, never hard-coded", () => {
    renderDialog({ message: `Are you sure you want to delete "CyberChef"?` });
    expect(screen.getByText('Are you sure you want to delete "CyberChef"?')).toBeInTheDocument();
  });

  it("shows a different repository's name just as dynamically", () => {
    renderDialog({ message: `Are you sure you want to delete "Trio.AI"?` });
    expect(screen.getByText('Are you sure you want to delete "Trio.AI"?')).toBeInTheDocument();
  });

  it("Cancel closes without confirming", async () => {
    const user = userEvent.setup();
    const { onClose, onConfirm } = renderDialog();

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("Escape closes without confirming", async () => {
    const user = userEvent.setup();
    const { onClose, onConfirm } = renderDialog();

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("clicking the backdrop closes without confirming", async () => {
    const user = userEvent.setup();
    const { onClose, onConfirm } = renderDialog();

    // The backdrop is the only element with aria-hidden — the click target
    // for "outside the dialog".
    const backdrop = document.querySelector('[aria-hidden="true"]');
    expect(backdrop).toBeTruthy();
    await user.click(backdrop as Element);

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("Delete triggers the confirm callback exactly once per click", async () => {
    const user = userEvent.setup();
    const { onConfirm } = renderDialog();

    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state and disables both buttons while deletion is in progress", () => {
    renderDialog({ isLoading: true });

    expect(screen.getByText("Deleting...")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("ignores Escape while deletion is in progress, so an in-flight delete cannot be silently abandoned", async () => {
    const user = userEvent.setup();
    const { onClose } = renderDialog({ isLoading: true });

    await user.keyboard("{Escape}");

    expect(onClose).not.toHaveBeenCalled();
  });

  it("does not allow a second Delete click to fire while the first is still loading", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Delete Repository"
        message='Are you sure you want to delete "acme-widgets"?'
        isLoading={false}
      />
    );

    const onConfirm = vi.fn();
    rerender(
      <ConfirmDialog
        isOpen
        onClose={vi.fn()}
        onConfirm={onConfirm}
        title="Delete Repository"
        message='Are you sure you want to delete "acme-widgets"?'
        confirmLabel="Delete"
        loadingLabel="Deleting..."
        isLoading
      />
    );

    // Once isLoading is true, the confirm button is replaced by a disabled
    // loading control — there is no clickable "Delete" to spam.
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    await user.click(screen.getByText("Deleting...").closest("button")!);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("surfaces a failure message without silently failing, and keeps the dialog open for retry", () => {
    renderDialog({ isLoading: false, error: "Failed to delete repository. Please try again." });

    expect(screen.getByText("Failed to delete repository. Please try again.")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    // Retry must still be possible.
    expect(screen.getByRole("button", { name: "Delete" })).toBeEnabled();
  });
});
