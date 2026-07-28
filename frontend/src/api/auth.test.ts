import {
  createApiKey,
  getSession,
  listApiKeys,
  login,
  logout,
  revokeApiKey,
} from "./auth";
import { setCsrfToken } from "./client";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("auth API", () => {
  afterEach(() => setCsrfToken(null));

  it("keeps session credentials in cookies and sends in-memory CSRF", async () => {
    const oneTimeValue = "synthetic-one-time-key";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({
          authenticated: true,
          user: { id: "owner-1", username: "owner" },
          csrf_token: "csrf-only-in-memory",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          api_key: oneTimeValue,
          key: {
            id: "key-1",
            name: "Codex",
            prefix: "prefix",
            scopes: ["library:read"],
            created_at: "2026-07-28T00:00:00Z",
            last_used_at: null,
            expires_at: null,
            revoked_at: null,
          },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await getSession();
    await createApiKey({ name: "Codex", scopes: ["library:read"] });
    await revokeApiKey("key-1");

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      credentials: "include",
    });
    const createInit = fetchMock.mock.calls[1]?.[1];
    expect(createInit?.method).toBe("POST");
    expect(createInit?.credentials).toBe("include");
    expect(new Headers(createInit?.headers).get("X-CSRF-Token")).toBe(
      "csrf-only-in-memory",
    );
    const revokeInit = fetchMock.mock.calls[2]?.[1];
    expect(revokeInit?.method).toBe("DELETE");
    expect(new Headers(revokeInit?.headers).get("X-CSRF-Token")).toBe(
      "csrf-only-in-memory",
    );
  });

  it("logs in, lists keys, and clears the session on logout", async () => {
    const key = {
      id: "key-2",
      name: "Read only",
      prefix: "readonly",
      scopes: ["library:read"],
      created_at: "2026-07-28T00:00:00Z",
      last_used_at: null,
      expires_at: null,
      revoked_at: null,
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({
          user: { id: "owner-1", username: "owner" },
          csrf_token: "login-csrf",
          expires_at: "2026-08-04T00:00:00Z",
        }),
      )
      .mockResolvedValueOnce(jsonResponse([key]))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(login("owner", "safe-password")).resolves.toMatchObject({
      authenticated: true,
      csrf_token: "login-csrf",
    });
    await expect(listApiKeys()).resolves.toEqual([key]);
    await logout();

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/auth/login");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/auth/api-keys");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/auth/logout");
    expect(
      new Headers(fetchMock.mock.calls[2]?.[1]?.headers).get("X-CSRF-Token"),
    ).toBe("login-csrf");
  });
});
