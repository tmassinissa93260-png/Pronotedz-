import { supabase } from "@/lib/supabase/client";

export async function startCheckout(itemType: "course" | "session", itemId: string): Promise<{ checkoutUrl: string; paymentId: string }> {
  const { data, error } = await supabase.functions.invoke("chargily-checkout", { body: { itemType, itemId } });
  if (error) throw new Error(error.message ?? "Impossible de démarrer le paiement.");
  if (data?.error) throw new Error(data.error);
  return data;
}
