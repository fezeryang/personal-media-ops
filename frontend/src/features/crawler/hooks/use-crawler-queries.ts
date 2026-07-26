import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  cancelCrawlerTask,
  createCrawlerTask,
  getCrawlerCapabilities,
  getCrawlerTask,
  getCrawlerTaskLogs,
  getCrawlerTaskQrcode,
  getCrawlerTaskResults,
  listCrawlerTasks,
  type CreateCrawlerTaskInput,
  type CrawlerTask,
} from "../../../api/crawler";
import { ApiError } from "../../../api/client";
import { getHealth } from "../../../api/health";
import { isActiveTask } from "../lib/task";

export const crawlerQueryKeys = {
  capabilities: ["crawler-capabilities"] as const,
  all: ["crawler-tasks"] as const,
  detail: (taskId: string) => ["crawler-tasks", taskId] as const,
  logs: (taskId: string) => ["crawler-tasks", taskId, "logs"] as const,
  qrcode: (taskId: string) => ["crawler-tasks", taskId, "qrcode"] as const,
  results: (taskId: string, offset: number, limit: number) =>
    ["crawler-tasks", taskId, "results", offset, limit] as const,
};

export function useCrawlerCapabilitiesQuery() {
  return useQuery({
    queryKey: crawlerQueryKeys.capabilities,
    queryFn: ({ signal }) => getCrawlerCapabilities(signal),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
}

export function useHealthQuery() {
  return useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => getHealth(signal),
    refetchInterval: 30_000,
  });
}

export function useCrawlerTasksQuery() {
  return useQuery({
    queryKey: crawlerQueryKeys.all,
    queryFn: ({ signal }) => listCrawlerTasks(signal),
    refetchInterval: (query) =>
      query.state.data?.some(isActiveTask) ? 3_000 : 15_000,
  });
}

export function useCrawlerTaskQuery(taskId: string) {
  return useQuery({
    queryKey: crawlerQueryKeys.detail(taskId),
    queryFn: ({ signal }) => getCrawlerTask(taskId, signal),
    enabled: Boolean(taskId),
    refetchInterval: (query) =>
      query.state.data && isActiveTask(query.state.data) ? 2_000 : false,
  });
}

export function useCrawlerTaskLogsQuery(
  taskId: string,
  active: boolean,
  autoRefresh: boolean,
) {
  return useQuery({
    queryKey: crawlerQueryKeys.logs(taskId),
    queryFn: async ({ signal }) => {
      try {
        return await getCrawlerTaskLogs(taskId, 300, signal);
      } catch (error: unknown) {
        if (error instanceof ApiError && error.status === 404) return "";
        throw error;
      }
    },
    enabled: Boolean(taskId),
    refetchInterval: active && autoRefresh ? 2_000 : false,
  });
}

export function useCrawlerTaskQrcodeQuery(
  taskId: string,
  waitingForLogin: boolean,
) {
  return useQuery({
    queryKey: crawlerQueryKeys.qrcode(taskId),
    queryFn: ({ signal }) => getCrawlerTaskQrcode(taskId, signal),
    enabled: Boolean(taskId) && waitingForLogin,
    refetchInterval: waitingForLogin ? 1_500 : false,
    staleTime: 0,
    gcTime: 0,
  });
}

export function useCrawlerResultsQuery(
  taskId: string,
  offset: number,
  limit: number,
  active: boolean,
) {
  return useQuery({
    queryKey: crawlerQueryKeys.results(taskId, offset, limit),
    queryFn: ({ signal }) =>
      getCrawlerTaskResults(taskId, offset, limit, signal),
    enabled: Boolean(taskId),
    placeholderData: (previous) => previous,
    refetchInterval: active ? 5_000 : false,
  });
}

function updateTaskCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  task: CrawlerTask,
): void {
  queryClient.setQueryData(crawlerQueryKeys.detail(task.id), task);
  queryClient.setQueryData<CrawlerTask[]>(
    crawlerQueryKeys.all,
    (current = []) => {
      const withoutTask = current.filter((item) => item.id !== task.id);
      return [task, ...withoutTask];
    },
  );
}

export function useCreateCrawlerTaskMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateCrawlerTaskInput) => createCrawlerTask(input),
    onSuccess: (task) => updateTaskCaches(queryClient, task),
  });
}

export function useCancelCrawlerTaskMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => cancelCrawlerTask(taskId),
    onSuccess: (task) => {
      updateTaskCaches(queryClient, task);
      void queryClient.invalidateQueries({
        queryKey: crawlerQueryKeys.detail(task.id),
      });
    },
  });
}
