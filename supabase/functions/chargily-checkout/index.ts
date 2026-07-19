// Supabase Edge Function: chargily-checkout
//
// Creates a Chargily Pay v2 checkout for a paid course or live session and
// records a pending `payments` row before redirecting the student. The
// price is always re-read from the DB server-side — the client only sends
// which item it wants, never an amount, so nothing can be tampered with in
// the browser.
//
// Body: { itemType: "course" | "session", itemId: string }
// Response: { checkoutUrl: string, paymentId: string }
//
// Required secrets:
//   CHARGILY_SECRET_KEY  - from the Chargily Pay dashboard (test or live)
//   CHARGILY_BASE_URL    - defaults to the Chargily *test* API; set to
//                           https://pay.chargily.net/api/v2 to go live
//   APP_URL               - your deployed app origin, e.g. https://estadi.dz
//                           (used to build the success/failure redirect URLs)
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY are automatic.
//
// Deploy: `supabase functions deploy chargily-checkout`

import { createClient } from "jsr:@supabase/supabase-js@2";

const CHARGILY_SECRET_KEY = Deno.env.get("CHARGILY_SECRET_KEY") ?? "";
const CHARGILY_BASE_URL = Deno.env.get("CHARGILY_BASE_URL") ?? "https://pay.chargily.net/test/api/v2";
const APP_URL = Deno.env.get("APP_URL") ?? "";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    if (!CHARGILY_SECRET_KEY) return jsonResponse({ error: "CHARGILY_SECRET_KEY n'est pas configurée." }, 500);
    if (!APP_URL) return jsonResponse({ error: "APP_URL n'est pas configurée." }, 500);

    const authHeader = req.headers.get("Authorization") ?? "";
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    const userClient = createClient(supabaseUrl, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: userData, error: userError } = await userClient.auth.getUser();
    if (userError || !userData.user) return jsonResponse({ error: "Authentification requise." }, 401);
    const userId = userData.user.id;

    const db = createClient(supabaseUrl, serviceRoleKey);

    const body = await req.json();
    const itemType = body.itemType as "course" | "session";
    const itemId = body.itemId as string;
    if (itemType !== "course" && itemType !== "session") return jsonResponse({ error: "itemType invalide." }, 400);

    let amount: number;
    let description: string;

    if (itemType === "course") {
      const { data: course, error } = await db.from("courses").select("id, title, price, status").eq("id", itemId).single();
      if (error || !course) return jsonResponse({ error: "Cours introuvable." }, 404);
      if (course.status !== "published") return jsonResponse({ error: "Ce cours n'est plus disponible." }, 400);
      if (course.price <= 0) return jsonResponse({ error: "Ce cours est gratuit — pas de paiement nécessaire." }, 400);
      amount = course.price;
      description = `Cours: ${course.title}`;
    } else {
      const { data: session, error } = await db
        .from("live_sessions")
        .select("id, title, subject, price_per_student, status, scheduled_at")
        .eq("id", itemId)
        .single();
      if (error || !session) return jsonResponse({ error: "Session introuvable." }, 404);
      if (session.status === "cancelled" || session.status === "completed") return jsonResponse({ error: "Cette session n'est plus disponible." }, 400);
      if (new Date(session.scheduled_at).getTime() < Date.now()) return jsonResponse({ error: "Ce créneau est déjà passé." }, 400);
      if (session.price_per_student <= 0) return jsonResponse({ error: "Cette session est gratuite — pas de paiement nécessaire." }, 400);
      amount = session.price_per_student;
      description = `Session: ${session.title ?? session.subject}`;
    }

    const { data: payment, error: paymentError } = await db
      .from("payments")
      .insert({ user_id: userId, item_type: itemType, item_id: itemId, amount, currency: "dzd", status: "pending" })
      .select("id")
      .single();
    if (paymentError) return jsonResponse({ error: paymentError.message }, 500);

    const checkoutRes = await fetch(`${CHARGILY_BASE_URL}/checkouts`, {
      method: "POST",
      headers: { Authorization: `Bearer ${CHARGILY_SECRET_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        amount,
        currency: "dzd",
        description,
        success_url: `${APP_URL}/payment/success?payment_id=${payment.id}`,
        failure_url: `${APP_URL}/payment/cancel?payment_id=${payment.id}`,
        metadata: { payment_id: payment.id },
      }),
    });
    if (!checkoutRes.ok) {
      const text = await checkoutRes.text();
      await db.from("payments").update({ status: "failed" }).eq("id", payment.id);
      return jsonResponse({ error: `Chargily a refusé la création du paiement (${checkoutRes.status}): ${text.slice(0, 300)}` }, 502);
    }
    const checkout = await checkoutRes.json();

    await db
      .from("payments")
      .update({ chargily_checkout_id: checkout.id, chargily_payment_url: checkout.checkout_url })
      .eq("id", payment.id);

    return jsonResponse({ checkoutUrl: checkout.checkout_url, paymentId: payment.id });
  } catch (err) {
    console.error("[chargily-checkout]", err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur inconnue." }, 500);
  }
});
