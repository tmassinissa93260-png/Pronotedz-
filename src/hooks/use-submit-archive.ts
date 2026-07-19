import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitArchiveEntry, type SubmitArchivePayload } from "@/lib/archive/submit";

export function useSubmitArchive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SubmitArchivePayload) => submitArchiveEntry(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["archive", "pending"] });
    },
  });
}
