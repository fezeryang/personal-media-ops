import { isLoginQrcodeFailure } from "./qrcode";

describe("isLoginQrcodeFailure", () => {
  it("recognizes a terminal login timeout", () => {
    expect(
      isLoginQrcodeFailure({
        status: "failed",
        error_message: "小红书 login timed out",
      }),
    ).toBe(true);
  });

  it("does not treat an active login task as terminal", () => {
    expect(
      isLoginQrcodeFailure({
        status: "waiting_login",
        error_message: "login timed out",
      }),
    ).toBe(false);
  });

  it("does not label unrelated crawler failures as QR failures", () => {
    expect(
      isLoginQrcodeFailure({
        status: "failed",
        error_message: "MediaCrawler exited with code 1",
      }),
    ).toBe(false);
  });
});
