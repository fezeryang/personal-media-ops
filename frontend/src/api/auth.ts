import { z } from "zod";

import {
  requestEmpty,
  requestJson,
  setCsrfToken,
} from "./client";

const userSchema = z.object({
  id: z.string(),
  username: z.string(),
});

const sessionSchema = z.object({
  authenticated: z.boolean(),
  user: userSchema.nullable(),
  csrf_token: z.string().nullable(),
});

const loginSchema = z.object({
  user: userSchema,
  csrf_token: z.string(),
  expires_at: z.string(),
});

export const apiKeySchema = z.object({
  id: z.string(),
  name: z.string(),
  prefix: z.string(),
  scopes: z.array(z.string()),
  created_at: z.string(),
  last_used_at: z.string().nullable(),
  expires_at: z.string().nullable(),
  revoked_at: z.string().nullable(),
});

const createdApiKeySchema = z.object({
  api_key: z.string(),
  key: apiKeySchema,
});

export type Session = z.infer<typeof sessionSchema>;
export type ApiKey = z.infer<typeof apiKeySchema>;
export type CreatedApiKey = z.infer<typeof createdApiKeySchema>;

export async function getSession(signal?: AbortSignal): Promise<Session> {
  const session = await requestJson("/api/auth/session", sessionSchema, {
    signal,
  });
  setCsrfToken(session.csrf_token);
  return session;
}

export async function login(
  username: string,
  password: string,
): Promise<Session> {
  const result = await requestJson("/api/auth/login", loginSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  setCsrfToken(result.csrf_token);
  return {
    authenticated: true,
    user: result.user,
    csrf_token: result.csrf_token,
  };
}

export async function logout(): Promise<void> {
  await requestEmpty("/api/auth/logout", { method: "POST" });
  setCsrfToken(null);
}

export function listApiKeys(signal?: AbortSignal): Promise<ApiKey[]> {
  return requestJson("/api/auth/api-keys", z.array(apiKeySchema), { signal });
}

export function createApiKey(input: {
  name: string;
  scopes: string[];
  expires_at?: string;
}): Promise<CreatedApiKey> {
  return requestJson("/api/auth/api-keys", createdApiKeySchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function revokeApiKey(id: string): Promise<void> {
  return requestEmpty(`/api/auth/api-keys/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
