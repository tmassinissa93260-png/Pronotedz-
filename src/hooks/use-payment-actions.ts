import { useMutation } from "@tanstack/react-query";
import { startCheckout } from "@/lib/payments/actions";

export function useStartCheckout() {
  return useMutation({
    mutationFn: ({ itemType, itemId }: { itemType: "course" | "session"; itemId: string }) => startCheckout(itemType, itemId),
  });
}
