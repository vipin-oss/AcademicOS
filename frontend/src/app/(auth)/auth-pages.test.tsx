/** Auth pages render test (final release): the login / register /
 * forgot-password / reset-password pages render their complete forms —
 * the required authentication UI is present and functional. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// --- mocks ----------------------------------------------------------------
const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams("token=test-token"),
}));

const login = vi.fn();
const register = vi.fn();

vi.mock("@/lib/auth/session", () => ({
  useAuth: () => ({ status: "anon", user: null, login, register, logout: vi.fn() }),
}));

beforeEach(() => {
  push.mockClear();
  replace.mockClear();
  login.mockClear();
  register.mockClear();
});

// --- tests ----------------------------------------------------------------
describe("authentication pages", () => {
  it("renders the login form", async () => {
    const { default: LoginPage } = await import("@/app/(auth)/login/page");
    render(<LoginPage />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByText("Forgot password?")).toBeInTheDocument();
  });

  it("submits credentials through the session provider", async () => {
    login.mockResolvedValue(undefined);
    const { default: LoginPage } = await import("@/app/(auth)/login/page");
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText("Username"), "alice");
    await userEvent.type(screen.getByLabelText("Password"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(login).toHaveBeenCalledWith("alice", "secret-pass");
  });

  it("renders the register form", async () => {
    const { default: RegisterPage } = await import("@/app/(auth)/register/page");
    render(<RegisterPage />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getAllByLabelText(/password/i).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });

  it("registers through the session provider", async () => {
    register.mockResolvedValue(undefined);
    const { default: RegisterPage } = await import("@/app/(auth)/register/page");
    render(<RegisterPage />);
    await userEvent.type(screen.getByLabelText("Username"), "bob");
    await userEvent.type(screen.getAllByLabelText(/password/i)[0], "bob-pass-123");
    await userEvent.type(screen.getAllByLabelText(/password/i)[1], "bob-pass-123");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(register).toHaveBeenCalledWith("bob", "bob-pass-123");
  });

  it("renders the forgot-password form", async () => {
    const { default: ForgotPasswordPage } = await import("@/app/(auth)/forgot-password/page");
    render(<ForgotPasswordPage />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Get reset token" })).toBeInTheDocument();
  });

  it("renders the reset-password form with the token", async () => {
    const { default: ResetPasswordPage } = await import("@/app/(auth)/reset-password/page");
    render(<ResetPasswordPage />);
    expect(screen.getByLabelText("Reset token")).toBeInTheDocument();
    expect(screen.getByLabelText(/New password/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset password" })).toBeInTheDocument();
  });
});
