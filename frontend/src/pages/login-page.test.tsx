import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

import * as authApi from "../api/auth";
import { AuthProvider } from "../features/auth/auth-context";
import { LoginPage } from "./login-page";

describe("LoginPage", () => {
  it("restores an anonymous session and logs the owner in", async () => {
    vi.spyOn(authApi, "getSession").mockResolvedValue({
      authenticated: false,
      user: null,
      csrf_token: null,
    });
    const login = vi.spyOn(authApi, "login").mockResolvedValue({
      authenticated: true,
      user: { id: "owner-1", username: "owner" },
      csrf_token: "csrf",
    });
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<p>安全工作台</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    await user.type(await screen.findByLabelText("用户名"), "owner");
    await user.type(screen.getByLabelText("密码"), "correct password");
    await user.click(screen.getByRole("button", { name: /进入工作台/ }));

    expect(login).toHaveBeenCalledWith("owner", "correct password");
    expect(await screen.findByText("安全工作台")).toBeInTheDocument();
  });

  it("renders authentication failures without exposing the password", async () => {
    vi.spyOn(authApi, "getSession").mockResolvedValue({
      authenticated: false,
      user: null,
      csrf_token: null,
    });
    vi.spyOn(authApi, "login").mockRejectedValue(
      new Error("Invalid username or password"),
    );
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </AuthProvider>,
    );

    await user.type(await screen.findByLabelText("用户名"), "owner");
    await user.type(screen.getByLabelText("密码"), "not-correct");
    await user.click(screen.getByRole("button", { name: /进入工作台/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "登录失败，请稍后重试",
    );
    expect(screen.queryByText("not-correct")).not.toBeInTheDocument();
  });
});
