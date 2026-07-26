import { z } from "zod";

import { requestJson } from "./client";

const healthSchema = z.object({
  status: z.literal("ok"),
  service: z.string(),
  version: z.string(),
});

export type HealthResponse = z.infer<typeof healthSchema>;

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson("/api/health", healthSchema, { signal });
}
