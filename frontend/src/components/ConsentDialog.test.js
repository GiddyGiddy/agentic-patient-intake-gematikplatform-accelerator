import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConsentDialog from "./ConsentDialog";

test("explains purpose, data and duration and focuses the grant button", () => {
  render(<ConsentDialog onDecision={jest.fn()} />);
  const dialog = screen.getByRole("dialog", { name: /Zugriff auf Ihre Daten/ });
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(screen.getByText(/Zweck:/)).toBeInTheDocument();
  expect(screen.getByText(/Medikationsplan/)).toBeInTheDocument();
  expect(screen.getByText(/Dauer:/)).toBeInTheDocument();
  expect(screen.getByText(/jederzeit widerrufen/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Mit Gesundheits-ID freigeben" })).toHaveFocus();
});

test("reports grant, decline and Escape", async () => {
  const onDecision = jest.fn();
  render(<ConsentDialog onDecision={onDecision} />);

  await userEvent.click(screen.getByRole("button", { name: "Mit Gesundheits-ID freigeben" }));
  expect(onDecision).toHaveBeenLastCalledWith(true);

  await userEvent.click(screen.getByRole("button", { name: "Nicht freigeben" }));
  expect(onDecision).toHaveBeenLastCalledWith(false);

  await userEvent.keyboard("{Escape}");
  expect(onDecision).toHaveBeenCalledTimes(3);
  expect(onDecision).toHaveBeenLastCalledWith(false);
});
