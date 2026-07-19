import { useQuery } from "@tanstack/react-query";
import { dashboardQueryOptions } from "@/lib/queries/dashboard";

export function useDashboard(userId: string | undefined) {
  return useQuery(dashboardQueryOptions(userId));
}
