import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  archiveMonitoringMission,
  confirmMonitoringMission,
  createMonitoringMission,
  getMonitoringBaseline,
  getMonitoringMission,
  listMonitoringChanges,
  listMonitoringMissions,
  listMonitoringNotifications,
  listMonitoringRuns,
  pauseMonitoringMission,
  resumeMonitoringMission,
  runMonitoringMission,
  updateMonitoringNotification,
  type MonitoringMissionInput,
} from "../../../api/monitoring";

export const monitoringQueryKeys = {
  all: ["monitoring"] as const,
  missions: ["monitoring", "missions"] as const,
  mission: (id: string) => ["monitoring", "mission", id] as const,
  runs: (id: string) => ["monitoring", "mission", id, "runs"] as const,
  changes: (id: string) => ["monitoring", "mission", id, "changes"] as const,
  baseline: (id: string) => ["monitoring", "mission", id, "baseline"] as const,
  notifications: ["monitoring", "notifications"] as const,
};

export function useMonitoringMissionsQuery() {
  return useQuery({
    queryKey: monitoringQueryKeys.missions,
    queryFn: ({ signal }) => listMonitoringMissions(signal),
    refetchInterval: 30_000,
  });
}

export function useMonitoringMissionQuery(missionId: string) {
  return useQuery({
    queryKey: monitoringQueryKeys.mission(missionId),
    queryFn: ({ signal }) => getMonitoringMission(missionId, signal),
    enabled: Boolean(missionId),
  });
}

export function useMonitoringRunsQuery(missionId: string, enabled = true) {
  return useQuery({
    queryKey: monitoringQueryKeys.runs(missionId),
    queryFn: ({ signal }) => listMonitoringRuns(missionId, signal),
    enabled: Boolean(missionId) && enabled,
    refetchInterval: 15_000,
  });
}

export function useMonitoringChangesQuery(missionId: string, enabled = true) {
  return useQuery({
    queryKey: monitoringQueryKeys.changes(missionId),
    queryFn: ({ signal }) => listMonitoringChanges(missionId, signal),
    enabled: Boolean(missionId) && enabled,
  });
}

export function useMonitoringBaselineQuery(missionId: string, enabled = true) {
  return useQuery({
    queryKey: monitoringQueryKeys.baseline(missionId),
    queryFn: ({ signal }) => getMonitoringBaseline(missionId, signal),
    enabled: Boolean(missionId) && enabled,
  });
}

export function useMonitoringNotificationsQuery() {
  return useQuery({
    queryKey: monitoringQueryKeys.notifications,
    queryFn: ({ signal }) => listMonitoringNotifications(signal),
    refetchInterval: 30_000,
  });
}

function invalidateMission(queryClient: ReturnType<typeof useQueryClient>, missionId: string) {
  void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.missions });
  void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.mission(missionId) });
  void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.runs(missionId) });
  void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.changes(missionId) });
  void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.baseline(missionId) });
  void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.notifications });
}

export function useCreateMonitoringMissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: MonitoringMissionInput) => createMonitoringMission(input),
    onSuccess: (mission) => {
      queryClient.setQueryData(monitoringQueryKeys.mission(mission.id), mission);
      void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.missions });
    },
  });
}

export function useConfirmMonitoringMissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (missionId: string) => confirmMonitoringMission(missionId),
    onSuccess: (mission) => invalidateMission(queryClient, mission.id),
  });
}

export function useRunMonitoringMissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (missionId: string) => runMonitoringMission(missionId),
    onSuccess: (result) => invalidateMission(queryClient, result.mission_id),
  });
}

function useMissionControlMutation(action: "pause" | "resume" | "archive") {
  const queryClient = useQueryClient();
  const actions = {
    pause: pauseMonitoringMission,
    resume: resumeMonitoringMission,
    archive: archiveMonitoringMission,
  } as const;
  return useMutation({
    mutationFn: (missionId: string) => actions[action](missionId),
    onSuccess: (mission) => invalidateMission(queryClient, mission.id),
  });
}

export const usePauseMonitoringMissionMutation = () => useMissionControlMutation("pause");
export const useResumeMonitoringMissionMutation = () => useMissionControlMutation("resume");
export const useArchiveMonitoringMissionMutation = () => useMissionControlMutation("archive");

export function useUpdateMonitoringNotificationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { notificationId: string; action: "read" | "defer" | "ignore"; until?: string }) =>
      updateMonitoringNotification(input.notificationId, input.action, input.until),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.notifications });
      void queryClient.invalidateQueries({ queryKey: monitoringQueryKeys.missions });
    },
  });
}
