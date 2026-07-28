import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as authApi from "../../api/auth";
import { AuthProvider, useAuth } from "./auth-context";

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <p>{auth.session?.authenticated ? "authenticated" : "anonymous"}</p>
      <button type="button" onClick={() => void auth.logout()}>
        logout
      </button>
    </div>
  );
}

describe("AuthProvider", () => {
  it("invalidates an expired session and logs out through the server", async () => {
    vi.spyOn(authApi, "getSession").mockResolvedValue({
      authenticated: true,
      user: { id: "owner-1", username: "owner" },
      csrf_token: "csrf",
    });
    const logout = vi.spyOn(authApi, "logout").mockResolvedValue();
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    expect(await screen.findByText("authenticated")).toBeInTheDocument();
    window.dispatchEvent(new Event("mediaops:unauthorized"));
    expect(await screen.findByText("anonymous")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "logout" }));
    expect(logout).toHaveBeenCalledOnce();
  });
});
