import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addDiscoveryToSpace,
  addResearchSpaceItem,
  continueDiscovery,
  createResearchSpace,
  getDiscovery,
  getResearchPreferences,
  getResearchSpace,
  giveDiscoveryFeedback,
  listDiscoveries,
  listResearchSpaces,
  listResearchSpaceItems,
  type DiscoveryFeedbackInput,
  type ResearchSpaceItemType,
} from "../../../api/research";
import { researchQueryKeys } from "./use-research-queries";

export const discoveryQueryKeys = {
  all: ["research-discoveries"] as const,
  list: (filters: { state?: string; researchTaskId?: string }) =>
    ["research-discoveries", "list", filters] as const,
  detail: (candidateId: string) => ["research-discoveries", candidateId] as const,
  spaces: ["research-spaces"] as const,
  space: (spaceId: string) => ["research-spaces", spaceId] as const,
  spaceItems: (filters: { itemType?: ResearchSpaceItemType; query?: string }) => ["research-space-items", filters] as const,
  preferences: ["research-preferences"] as const,
};

export function useDiscoveriesQuery(filters: { state?: string; researchTaskId?: string } = {}) {
  return useQuery({
    queryKey: discoveryQueryKeys.list(filters),
    queryFn: ({ signal }) => listDiscoveries({ ...filters, limit: 100 }, signal),
    refetchInterval: 15_000,
  });
}

export function useDiscoveryQuery(candidateId: string, enabled = true) {
  return useQuery({
    queryKey: discoveryQueryKeys.detail(candidateId),
    queryFn: ({ signal }) => getDiscovery(candidateId, signal),
    enabled: Boolean(candidateId) && enabled,
  });
}

export function useResearchSpacesQuery() {
  return useQuery({
    queryKey: discoveryQueryKeys.spaces,
    queryFn: ({ signal }) => listResearchSpaces(signal),
  });
}

export function useResearchSpaceQuery(spaceId: string) {
  return useQuery({
    queryKey: discoveryQueryKeys.space(spaceId),
    queryFn: ({ signal }) => getResearchSpace(spaceId, signal),
    enabled: Boolean(spaceId),
  });
}

export function useResearchSpaceItemsQuery(filters: { itemType?: ResearchSpaceItemType; query?: string } = {}) {
  return useQuery({
    queryKey: discoveryQueryKeys.spaceItems(filters),
    queryFn: ({ signal }) => listResearchSpaceItems({ ...filters, limit: 80 }, signal),
    enabled: Boolean(filters.itemType || filters.query?.trim()),
  });
}

export function useResearchPreferencesQuery() {
  return useQuery({
    queryKey: discoveryQueryKeys.preferences,
    queryFn: ({ signal }) => getResearchPreferences(signal),
    staleTime: 60_000,
  });
}

function invalidateDiscovery(queryClient: ReturnType<typeof useQueryClient>, candidateId: string) {
  void queryClient.invalidateQueries({ queryKey: discoveryQueryKeys.all });
  void queryClient.invalidateQueries({ queryKey: discoveryQueryKeys.detail(candidateId) });
}

export function useDiscoveryFeedbackMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { candidateId: string; feedback: DiscoveryFeedbackInput }) =>
      giveDiscoveryFeedback(input.candidateId, input.feedback),
    onSuccess: (candidate) => invalidateDiscovery(queryClient, candidate.id),
  });
}

export function useContinueDiscoveryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { candidateId: string; request?: string }) =>
      continueDiscovery(input.candidateId, input.request),
    onSuccess: (task, input) => {
      invalidateDiscovery(queryClient, input.candidateId);
      queryClient.setQueryData(researchQueryKeys.detail(task.id), task);
      void queryClient.invalidateQueries({ queryKey: researchQueryKeys.all });
    },
  });
}

export function useAddDiscoveryToSpaceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { candidateId: string; spaceId: string; note?: string }) =>
      addDiscoveryToSpace(input.candidateId, { space_id: input.spaceId, note: input.note }),
    onSuccess: (item, input) => {
      invalidateDiscovery(queryClient, input.candidateId);
      void queryClient.invalidateQueries({ queryKey: discoveryQueryKeys.space(item.space_id) });
      void queryClient.invalidateQueries({ queryKey: discoveryQueryKeys.spaces });
    },
  });
}

export function useCreateResearchSpaceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; description?: string }) => createResearchSpace(input),
    onSuccess: (space) => {
      queryClient.setQueryData(discoveryQueryKeys.space(space.id), space);
      void queryClient.invalidateQueries({ queryKey: discoveryQueryKeys.spaces });
    },
  });
}

export function useAddResearchSpaceItemMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { spaceId: string; itemType: ResearchSpaceItemType; itemId: string; note?: string }) =>
      addResearchSpaceItem(input.spaceId, {
        item_type: input.itemType,
        item_id: input.itemId,
        note: input.note,
      }),
    onSuccess: (item) => {
      void queryClient.invalidateQueries({ queryKey: discoveryQueryKeys.space(item.space_id) });
      void queryClient.invalidateQueries({ queryKey: discoveryQueryKeys.spaces });
    },
  });
}
