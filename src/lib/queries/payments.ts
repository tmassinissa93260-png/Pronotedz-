import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type Payment = Database["public"]["Tables"]["payments"]["Row"];

async function fetchPayment(paymentId: string): Promise<Payment | null> {
  const { data, error } = await supabase.from("payments").select("*").eq("id", paymentId).maybeSingle();
  if (error) throw error;
  return data;
}

/** Polls briefly right after redirect back from Chargily, while the webhook lands. */
export function paymentQueryOptions(paymentId: string | undefined) {
  return queryOptions({
    queryKey: ["payments", "detail", paymentId],
    queryFn: () => fetchPayment(paymentId as string),
    enabled: Boolean(paymentId),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 2_000 : false),
  });
}
