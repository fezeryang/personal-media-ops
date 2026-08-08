import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addOpportunityToSpace,
  analyzeOpportunity,
  approveValidationPlan,
  createOpportunityAction,
  createValidationPlan,
  getOpportunity,
  listOpportunities,
  recordOpportunityOutcome,
  recordValidationResult,
  startValidationResearch,
  submitOpportunityFeedback,
  updateOpportunityAction,
} from "../../../api/opportunity";

export function useOpportunitiesQuery() {
  return useQuery({ queryKey: ["opportunities"], queryFn: ({ signal }) => listOpportunities(signal) });
}

export function useOpportunityQuery(opportunityId: string) {
  return useQuery({ queryKey: ["opportunity", opportunityId], queryFn: ({ signal }) => getOpportunity(opportunityId, signal), enabled: Boolean(opportunityId) });
}

function invalidateOpportunities(queryClient: ReturnType<typeof useQueryClient>, opportunityId?: string) {
  void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
  if (opportunityId) void queryClient.invalidateQueries({ queryKey: ["opportunity", opportunityId] });
}

export function useAnalyzeOpportunityMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: analyzeOpportunity,
    onSuccess: () => invalidateOpportunities(queryClient),
  });
}

export function useOpportunityFeedbackMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { feedback_type: string; note?: string }) => submitOpportunityFeedback(opportunityId, input),
    onSuccess: () => invalidateOpportunities(queryClient, opportunityId),
  });
}

export function useCreateValidationPlanMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Record<string, unknown> = {}) => createValidationPlan(opportunityId, input),
    onSuccess: () => invalidateOpportunities(queryClient, opportunityId),
  });
}

export function useApproveValidationPlanMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => approveValidationPlan(planId),
    onSuccess: () => invalidateOpportunities(queryClient, opportunityId),
  });
}

export function useStartValidationResearchMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => startValidationResearch(planId),
    onSuccess: () => invalidateOpportunities(queryClient, opportunityId),
  });
}

export function useRecordValidationResultMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { planId: string; values: Record<string, unknown> }) => recordValidationResult(input.planId, input.values),
    onSuccess: () => invalidateOpportunities(queryClient, opportunityId),
  });
}

export function useCreateOpportunityActionMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Record<string, unknown>) => createOpportunityAction(input),
    onSuccess: () => invalidateOpportunities(queryClient, opportunityId),
  });
}

export function useUpdateOpportunityActionMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { actionId: string; status: string; user_notes?: string }) => updateOpportunityAction(input.actionId, { status: input.status, user_notes: input.user_notes }),
    onSuccess: () => invalidateOpportunities(queryClient, opportunityId),
  });
}

export function useRecordOpportunityOutcomeMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { actionId: string; values: Record<string, unknown> }) => recordOpportunityOutcome(input.actionId, input.values),
    onSuccess: () => invalidateOpportunities(queryClient, opportunityId),
  });
}

export function useAddOpportunityToSpaceMutation(opportunityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { spaceId: string; note?: string }) => addOpportunityToSpace(opportunityId, input.spaceId, input.note),
    onSuccess: () => {
      invalidateOpportunities(queryClient, opportunityId);
      void queryClient.invalidateQueries({ queryKey: ["research-spaces"] });
    },
  });
}
