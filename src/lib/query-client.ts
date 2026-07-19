import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        // Don't burn retries on auth/permission errors — only on transient network failures.
        const message = error instanceof Error ? error.message.toLowerCase() : "";
        if (message.includes("jwt") || message.includes("permission") || message.includes("rls")) {
          return false;
        }
        return failureCount < 3;
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
    },
    mutations: {
      retry: 1,
    },
  },
});
