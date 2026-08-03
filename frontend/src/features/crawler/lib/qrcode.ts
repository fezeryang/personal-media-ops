import type { CrawlerTask } from "../../../api/crawler";

const LOGIN_FAILURE_PATTERN = /(login|登录|captcha|验证码|二维码)/i;

export function isLoginQrcodeFailure(
  task: Pick<CrawlerTask, "status" | "error_message">,
): boolean {
  return (
    task.status === "failed" &&
    LOGIN_FAILURE_PATTERN.test(task.error_message ?? "")
  );
}
