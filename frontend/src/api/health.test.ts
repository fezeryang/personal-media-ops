import { getHealth } from "./health";

describe("health API", () => {
  it("reads the deployed service identity", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          service: "personal-media-ops-api",
          version: "0.1.0",
        }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    await expect(getHealth()).resolves.toEqual({
      status: "ok",
      service: "personal-media-ops-api",
      version: "0.1.0",
    });
  });
});
