import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelResearchTask,
  completeResearchTask,
  createResearchTask,
  decideResearchAction,
  getResearchTask,
  listResearchTasks,
  pauseResearchTask,
  rerunResearchTask,
  resumeResearchTask,
  type ResearchTaskInput,
} from "../../../api/research";

export const researchQueryKeys = {
  all: ["research-tasks"] as const,
  detail: (taskId: string) => ["research-tasks", taskId] as const,
};

const activeStatuses = new Set([
  "Draft",
  "Planning",
  "Researching",
  "WaitingCrawl",
  "WaitingLogin",
  "Summarizing",
  "BudgetExceeded",
]);

export function useResearchTasksQuery() {
  return useQuery({
    queryKey: researchQueryKeys.all,
    queryFn: ({ signal }) => listResearchTasks(signal),
    refetchInterval: (query) =>
      query.state.data?.some((task) => activeStatuses.has(task.status))
        ? 2_000
        : 15_000,
  });
}

export function useResearchTaskQuery(taskId: string) {
  return useQuery({
    queryKey: researchQueryKeys.detail(taskId),
    queryFn: ({ signal }) => getResearchTask(taskId, signal),
    enabled: Boolean(taskId),
    refetchInterval: (query) =>
      query.state.data && activeStatuses.has(query.state.data.status)
        ? 2_000
        : false,
  });
}

function updateCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  task: Awaited<ReturnType<typeof getResearchTask>>,
) {
  queryClient.setQueryData(researchQueryKeys.detail(task.id), task);
  queryClient.setQueryData<Awaited<ReturnType<typeof listResearchTasks>>>(
    researchQueryKeys.all,
    (current = []) => {
      const without = current.filter((item) => item.id !== task.id);
      return [
        {
          id: task.id,
          task_type: task.task_type,
          objective: task.objective,
          platforms: task.platforms,
          status: task.status,
          current_round: task.current_round,
          current_step: task.current_step,
          paused: task.paused,
          consumption: task.consumption,
          finding_count: task.finding_count,
          event_count: task.event_count,
          action_count: task.action_count,
          created_at: task.created_at,
          updated_at: task.updated_at,
          finished_at: task.finished_at,
          failure_reason: task.failure_reason,
        },
        ...without,
      ];
    },
  );
}

export function useCreateResearchTaskMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ResearchTaskInput) => createResearchTask(input),
    onSuccess: (task) => updateCaches(queryClient, task),
  });
}

function useControlMutation(
  action: "pause" | "resume" | "cancel" | "rerun",
) {
  const queryClient = useQueryClient();
  const mutation = {
    pause: pauseResearchTask,
    resume: resumeResearchTask,
    cancel: cancelResearchTask,
    rerun: rerunResearchTask,
  }[action];
  return useMutation({
    mutationFn: (taskId: string) => mutation(taskId),
    onSuccess: (task) => updateCaches(queryClient, task),
  });
}

export const usePauseResearchTaskMutation = () => useControlMutation("pause");
export const useResumeResearchTaskMutation = () => useControlMutation("resume");
export const useCancelResearchTaskMutation = () => useControlMutation("cancel");
export const useRerunResearchTaskMutation = () => useControlMutation("rerun");

export function useCompleteResearchTaskMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => completeResearchTask(taskId),
    onSuccess: (task) => updateCaches(queryClient, task),
  });
}

export function useDecideResearchActionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      taskId: string;
      actionId: string;
      decision: "approve" | "reject";
    }) => decideResearchAction(input.taskId, input.actionId, input.decision),
    onSuccess: (_action, input) => {
      void queryClient.invalidateQueries({
        queryKey: researchQueryKeys.detail(input.taskId),
      });
      void queryClient.invalidateQueries({ queryKey: researchQueryKeys.all });
    },
  });
}
