import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type Referral = Database["public"]["Tables"]["referrals"]["Row"];

export type ReferralStatus = {
  referralCode: string | null;
  perkUnlockedUntil: string | null;
  perkActive: boolean;
  referrals: Referral[];
  acceptedCount: number;
  rewardedCount: number;
};

async function fetchReferralStatus(userId: string): Promise<ReferralStatus> {
  const [{ data: sp }, { data: referrals }] = await Promise.all([
    supabase.from("student_profiles").select("referral_code, perk_unlocked_until").eq("user_id", userId).maybeSingle(),
    supabase.from("referrals").select("*").eq("referrer_id", userId).order("created_at", { ascending: false }),
  ]);

  const list = referrals ?? [];
  const perkUntil = sp?.perk_unlocked_until ? new Date(sp.perk_unlocked_until) : null;

  return {
    referralCode: sp?.referral_code ?? null,
    perkUnlockedUntil: sp?.perk_unlocked_until ?? null,
    perkActive: Boolean(perkUntil && perkUntil.getTime() > Date.now()),
    referrals: list,
    acceptedCount: list.filter((r) => r.status === "accepted").length,
    rewardedCount: list.filter((r) => r.status === "rewarded").length,
  };
}

export function referralStatusQueryOptions(userId: string | undefined) {
  return queryOptions({
    queryKey: ["referral", "status", userId],
    queryFn: () => fetchReferralStatus(userId as string),
    enabled: Boolean(userId),
    staleTime: 30_000,
  });
}
