import { z } from "zod";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? "";
export const API_BASE_URL = configuredBaseUrl.replace(/\/+$/, "");

const validationIssueSchema = z.object({
  loc: z.array(z.union([z.string(), z.number()])).optional(),
  msg: z.string(),
});

const errorPayloadSchema = z.object({
  detail: z.union([
    z.string(),
    z.array(validationIssueSchema),
  ]).optional(),
});

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function validationMessage(
  issues: z.infer<typeof validationIssueSchema>[],
): string {
  return issues
    .map((issue) => {
      const field = issue.loc?.at(-1);
      return field === undefined ? issue.msg : `${String(field)}：${issue.msg}`;
    })
    .join("；");
}

async function responseError(response: Response): Promise<ApiError> {
  const fallback = `请求失败（HTTP ${response.status}）`;
  const contentType = response.headers.get("content-type") ?? "";

  if (!contentType.includes("application/json")) {
    return new ApiError(response.status, fallback);
  }

  try {
    const parsed = errorPayloadSchema.safeParse(await response.json());
    if (!parsed.success || parsed.data.detail === undefined) {
      return new ApiError(response.status, fallback);
    }
    const detail = parsed.data.detail;
    return new ApiError(
      response.status,
      typeof detail === "string" ? detail : validationMessage(detail),
    );
  } catch {
    return new ApiError(response.status, fallback);
  }
}

async function fetchApi(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
    });
    if (!response.ok) {
      throw await responseError(response);
    }
    return response;
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(0, "无法连接服务，请检查网络后重试");
  }
}

export async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetchApi(path, init);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(502, "服务返回了无法识别的数据格式");
  }
  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiError(502, "服务返回了无法识别的数据格式");
  }
  return parsed.data;
}

export async function requestText(
  path: string,
  init: RequestInit = {},
): Promise<string> {
  const response = await fetchApi(path, {
    ...init,
    headers: {
      Accept: "text/plain",
      ...init.headers,
    },
  });
  return response.text();
}

export async function requestBlob(
  path: string,
  init: RequestInit = {},
): Promise<Blob> {
  const response = await fetchApi(path, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "image/png",
      ...init.headers,
    },
  });
  if (response.headers.get("content-type")?.split(";")[0] !== "image/png") {
    throw new ApiError(502, "服务返回的二维码格式无效");
  }
  return response.blob();
}
