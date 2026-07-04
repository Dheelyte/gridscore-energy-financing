import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/demoAccounts";

import { LoginPage } from "./LoginPage";

const login = vi.fn().mockResolvedValue(undefined);
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ login }) }));

const renderPage = () =>
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );

describe("LoginPage accessibility", () => {
  it("exposes accessible names for the form controls", () => {
    renderPage();
    // Inputs are reachable by their accessible name (aria-label), not just placeholder.
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });
});

describe("LoginPage demo logins", () => {
  it("renders a one-click login for every demo role", () => {
    renderPage();
    for (const acct of DEMO_ACCOUNTS) {
      expect(screen.getByRole("button", { name: `Enter as ${acct.label}` })).toBeInTheDocument();
    }
  });

  it("signs in with the demo credentials when a role is clicked", async () => {
    login.mockClear();
    renderPage();
    const analyst = DEMO_ACCOUNTS[0];
    fireEvent.click(screen.getByRole("button", { name: `Enter as ${analyst.label}` }));
    await waitFor(() => expect(login).toHaveBeenCalledWith(analyst.email, DEMO_PASSWORD));
  });
});
