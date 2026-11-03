import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Chat from "./Chat";
import { ApiError, sendChat } from "../services/api";

jest.mock("../services/api", () => ({
  sendChat: jest.fn(),
  ApiError: class ApiError extends Error {
    constructor(status) {
      super(`Backend error ${status}`);
      this.status = status;
    }
  },
}));

const RED_PENDING = {
  reply: "Bitte rufen Sie sofort den Notruf 112.",
  triage_score: "Rot",
  anamnesis_summary: "Brustschmerzen",
  iam_required: true,
  iam_message: "Bitte Zugriff freigeben.",
};
const BOOKED = {
  reply: null,
  triage_score: "Rot",
  anamnesis_summary: "Brustschmerzen",
  iam_required: false,
  appointment_id: "a1",
  slot_start: "2030-01-01T10:00:00Z",
  kim_sent: true,
};

async function send(text) {
  await userEvent.type(screen.getByLabelText("Ihre Nachricht"), text);
  await userEvent.click(screen.getByRole("button", { name: "Senden" }));
}

beforeEach(() => {
  sessionStorage.clear();
  sendChat.mockReset();
});

test("emergency: banner, consent dialog, then resume with consent and show result", async () => {
  sendChat.mockResolvedValueOnce(RED_PENDING).mockResolvedValueOnce(BOOKED);
  render(<Chat token="tok" onUnauthorized={jest.fn()} />);

  await send("Ich habe Brustschmerzen");

  expect(await screen.findByRole("dialog")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "112 anrufen" })).toHaveAttribute("href", "tel:112");
  expect(sendChat).toHaveBeenCalledWith("tok", {
    message: "Ich habe Brustschmerzen",
    history: [],
    consent_granted: false,
  });

  await userEvent.click(screen.getByRole("button", { name: "Mit Gesundheits-ID freigeben" }));

  expect(await screen.findByRole("heading", { name: "Ihre Aufnahme ist abgeschlossen" })).toBeInTheDocument();
  expect(sendChat).toHaveBeenLastCalledWith(
    "tok",
    expect.objectContaining({
      consent_granted: true,
      triage_score: "Rot",
      anamnesis_summary: "Brustschmerzen",
    })
  );
  expect(screen.getByText(/Rot – Sofort/)).toBeInTheDocument();
  expect(screen.getByText(/per KIM/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Ihre Nachricht")).not.toBeInTheDocument();
});

test("declining shows feedback, sends nothing further and allows reconsidering", async () => {
  sendChat.mockResolvedValueOnce(RED_PENDING);
  render(<Chat token="tok" onUnauthorized={jest.fn()} />);
  await send("Brustschmerzen");

  await userEvent.click(await screen.findByRole("button", { name: "Nicht freigeben" }));

  expect(screen.getByText(/Keine Freigabe erteilt/)).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(sendChat).toHaveBeenCalledTimes(1);

  await userEvent.click(screen.getByRole("button", { name: "Freigabe erneut prüfen" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});

test("follow-up question keeps the conversation going and sends patient history", async () => {
  sendChat
    .mockResolvedValueOnce({ reply: "Seit wann?", iam_required: false })
    .mockResolvedValueOnce({ reply: "Danke.", triage_score: "Gelb", iam_required: true });
  render(<Chat token="tok" onUnauthorized={jest.fn()} />);

  await send("Husten");
  expect(await screen.findByText("Seit wann?")).toBeInTheDocument();
  await send("seit drei Tagen");

  await screen.findByRole("dialog");
  expect(sendChat).toHaveBeenLastCalledWith("tok", {
    message: "seit drei Tagen",
    history: ["Husten"],
    consent_granted: false,
  });
  expect(screen.queryByRole("link", { name: "112 anrufen" })).not.toBeInTheDocument();
});

test("errors are announced and can be retried", async () => {
  sendChat.mockRejectedValueOnce(new ApiError(500)).mockResolvedValueOnce({ reply: "Hallo", iam_required: false });
  render(<Chat token="tok" onUnauthorized={jest.fn()} />);
  await send("Hallo");

  expect(await screen.findByRole("alert")).toHaveTextContent("Code 500");
  await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));

  await waitFor(() => expect(screen.getAllByText("Hallo")).toHaveLength(2));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("network failure shows a connection message", async () => {
  sendChat.mockRejectedValueOnce(new ApiError(0));
  render(<Chat token="tok" onUnauthorized={jest.fn()} />);
  await send("Hallo");
  expect(await screen.findByRole("alert")).toHaveTextContent(/nicht erreichbar/);
});

test("a 401 from the backend triggers re-login", async () => {
  sendChat.mockRejectedValueOnce(new ApiError(401));
  const onUnauthorized = jest.fn();
  render(<Chat token="tok" onUnauthorized={onUnauthorized} />);
  await send("Hallo");
  await screen.findByLabelText("Ihre Nachricht");
  expect(onUnauthorized).toHaveBeenCalled();
});

test("consent can be revoked after granting", async () => {
  sendChat.mockResolvedValueOnce(RED_PENDING).mockResolvedValueOnce(BOOKED);
  render(<Chat token="tok" onUnauthorized={jest.fn()} />);
  await send("Brustschmerzen");
  await userEvent.click(await screen.findByRole("button", { name: "Mit Gesundheits-ID freigeben" }));
  await screen.findByText("Datenfreigabe erteilt");

  await userEvent.click(screen.getByRole("button", { name: "Freigabe widerrufen" }));

  expect(screen.queryByText("Datenfreigabe erteilt")).not.toBeInTheDocument();
  expect(screen.getByText(/Freigabe wurde widerrufen/)).toBeInTheDocument();
});

test("conversation survives a reload and restart clears it", async () => {
  sendChat.mockResolvedValueOnce({ reply: "Seit wann?", iam_required: false });
  const { unmount } = render(<Chat token="tok" onUnauthorized={jest.fn()} />);
  await send("Husten");
  await screen.findByText("Seit wann?");
  unmount();

  render(<Chat token="tok" onUnauthorized={jest.fn()} />);
  expect(screen.getByText("Husten")).toBeInTheDocument();
  expect(screen.getByText("Seit wann?")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Neues Gespräch" }));
  expect(screen.queryByText("Husten")).not.toBeInTheDocument();
});
