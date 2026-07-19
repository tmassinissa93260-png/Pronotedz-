import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitOnboarding, type OnboardingPayload } from "@/lib/onboarding/submit";

export function useOnboardingSubmit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OnboardingPayload) => submitOnboarding(payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["current-user", variables.userId] });
    },
  });
}
