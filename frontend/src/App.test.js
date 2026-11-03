import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import * as oidc from "./auth/oidc";

jest.mock("./components/Chat", () => ({ token, onUnauthorized }) => (
  <div>
    chat for {token}
    <button onClick={onUnauthorized}>unauthorized</button>
  </div>
));

function storeSession(expiresAt = Date.now() + 60_000) {
  sessionStorage.setItem(
    "intake.session",
    JSON.stringify({ accessToken: "tok", expiresAt, sub: "X110000001" })
  );
}

beforeEach(() => sessionStorage.clear());

test("without a session the login screen is shown", () => {
  render(<App />);
  expect(screen.getByRole("button", { name: "Mit Gesundheits-ID anmelden" })).toBeInTheDocument();
});

test("with a valid session the chat and user are shown", () => {
  storeSession();
  render(<App />);
  expect(screen.getByText("chat for tok")).toBeInTheDocument();
  expect(screen.getByText(/X110000001/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
});

test("an expired stored session leads to login", () => {
  storeSession(Date.now() - 1);
  render(<App />);
  expect(screen.getByRole("button", { name: "Mit Gesundheits-ID anmelden" })).toBeInTheDocument();
});

test("the session expires while the page is open", () => {
  jest.useFakeTimers();
  storeSession(Date.now() + 1000);
  render(<App />);
  expect(screen.getByText("chat for tok")).toBeInTheDocument();

  act(() => {
    jest.advanceTimersByTime(1500);
  });

  expect(screen.getByRole("status")).toHaveTextContent(/Sitzung ist abgelaufen/);
  expect(screen.getByRole("button", { name: "Mit Gesundheits-ID anmelden" })).toBeInTheDocument();
  jest.useRealTimers();
});

test("a 401 from the chat forces re-login", async () => {
  storeSession();
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "unauthorized" }));
  expect(screen.getByRole("button", { name: "Mit Gesundheits-ID anmelden" })).toBeInTheDocument();
  expect(sessionStorage.getItem("intake.session")).toBeNull();
});

test("a failed login callback shows an error", async () => {
  window.history.pushState({}, "", "/?error=access_denied&state=x");
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/Anmeldung ist fehlgeschlagen/);
  await waitFor(() => expect(window.location.search).toBe(""));
});

test("login button starts the OIDC flow", async () => {
  const spy = jest.spyOn(oidc, "login").mockResolvedValue();
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "Mit Gesundheits-ID anmelden" }));
  expect(spy).toHaveBeenCalled();
});
