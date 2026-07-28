import { useQuery } from "@tanstack/react-query";

import {
  getLibraryContent,
  getLibraryCreator,
  getLibraryStats,
  listLibraryContents,
  type ContentFilters,
} from "../../../api/library";

export const libraryQueryKeys = {
  stats: ["library", "stats"] as const,
  contents: (filters: ContentFilters) =>
    ["library", "contents", filters] as const,
  content: (contentId: string) => ["library", "contents", contentId] as const,
  creator: (creatorId: string) => ["library", "creators", creatorId] as const,
};

export function useLibraryStatsQuery() {
  return useQuery({
    queryKey: libraryQueryKeys.stats,
    queryFn: ({ signal }) => getLibraryStats(signal),
  });
}

export function useLibraryContentsQuery(filters: ContentFilters) {
  return useQuery({
    queryKey: libraryQueryKeys.contents(filters),
    queryFn: ({ signal }) => listLibraryContents(filters, signal),
    placeholderData: (previous) => previous,
  });
}

export function useLibraryContentQuery(contentId: string) {
  return useQuery({
    queryKey: libraryQueryKeys.content(contentId),
    queryFn: ({ signal }) => getLibraryContent(contentId, signal),
    enabled: Boolean(contentId),
  });
}

export function useLibraryCreatorQuery(creatorId: string) {
  return useQuery({
    queryKey: libraryQueryKeys.creator(creatorId),
    queryFn: ({ signal }) => getLibraryCreator(creatorId, signal),
    enabled: Boolean(creatorId),
  });
}
