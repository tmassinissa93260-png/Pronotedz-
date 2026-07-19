// Supabase Edge Function: chargily-webhook
//
// Public endpoint (no user JWT — Chargily calls this server-to-server).
// Verifies the HMAC-SHA256 `signature` header against CHARGILY_SECRET_KEY,
// then on a paid checkout: marks the payment paid, creates the
// course_enrollment / session_booking, and credits the teacher's earnings
// (minus the platform fee). Idempotent — replays of the same event are a
// safe no-op because it checks the payment isn't already 'paid' first.
//
// Configure in the Chargily dashboard: webhook URL = this function's URL,
// events = checkout.paid, checkout.failed.
//
// Required secrets:
//   CHARGILY_SECRET_KEY - same secret key used to create checkouts; also
//                          used as the webhook HMAC key by Chargily
//   PLATFORM_FEE_PCT     - optional, defaults to 15 (percent)
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are automatic.
//
// Deploy: `supabase functions deploy chargily-webhook --no-verify-jwt`

import { createClient } from "jsr:@supabase/supabase-js@2";

const CHARGILY_SECRET_KEY = Deno.env.get("CHARGILY_SECRET_KEY") ?? "";
const PLATFORM_FEE_PCT = Number(Deno.env.get("PLATFORM_FEE_PCT") ?? "15");

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

async function verifySignature(rawBody: string, signatureHeader: string | null): Promise<boolean> {
  if (!signatureHeader || !CHARGILY_SECRET_KEY) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(CHARGILY_SECRET_KEY),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(rawBody));
  const computed = Array.from(new Uint8Array(mac)).map((b) => b.toString(16).padStart(2, "0")).join("");
  if (computed.length !== signatureHeader.length) return false;
  let diff = 0;
  for (let i = 0; i < computed.length; i++) diff |= computed.charCodeAt(i) ^ signatureHeader.charCodeAt(i);
  return diff === 0;
}

Deno.serve(async (req) => {
  try {
    if (!CHARGILY_SECRET_KEY) return jsonResponse({ error: "CHARGILY_SECRET_KEY n'est pas configurée." }, 500);

    const rawBody = await req.text();
    const valid = await verifySignature(rawBody, req.headers.get("signature"));
    if (!valid) return jsonResponse({ error: "Signature invalide." }, 401);

    const event = JSON.parse(rawBody);
    const checkout = event.data;
    const checkoutId: string | undefined = checkout?.id;
    const paymentIdFromMetadata: string | undefined = checkout?.metadata?.payment_id;
    if (!checkoutId && !paymentIdFromMetadata) return jsonResponse({ error: "Payload sans identifiant de paiement." }, 400);

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const db = createClient(supabaseUrl, serviceRoleKey);

    let paymentQuery = db.from("payments").select("*");
    paymentQuery = paymentIdFromMetadata ? paymentQuery.eq("id", paymentIdFromMetadata) : paymentQuery.eq("chargily_checkout_id", checkoutId);
    const { data: payment, error: paymentError } = await paymentQuery.maybeSingle();
    if (paymentError || !payment) return jsonResponse({ error: "Paiement introuvable pour ce checkout." }, 404);

    if (event.type === "checkout.failed") {
      if (payment.status === "pending") await db.from("payments").update({ status: "failed" }).eq("id", payment.id);
      return jsonResponse({ ok: true });
    }

    if (event.type !== "checkout.paid") {
      return jsonResponse({ ok: true, ignored: event.type });
    }

    if (payment.status === "paid") {
      return jsonResponse({ ok: true, alreadyProcessed: true });
    }

    await db.from("payments").update({ status: "paid", paid_at: new Date().toISOString() }).eq("id", payment.id);

    let teacherId: string | null = null;
    let notifTitle = "";
    let notifLink = "";

    if (payment.item_type === "course") {
      const { data: course } = await db.from("courses").select("teacher_id, title").eq("id", payment.item_id).single();
      teacherId = course?.teacher_id ?? null;
      notifTitle = course?.title ?? "un cours";
      notifLink = `/courses/${payment.item_id}`;

      const { data: existing } = await db
        .from("course_enrollments")
        .select("id")
        .eq("course_id", payment.item_id)
        .eq("student_id", payment.user_id)
        .maybeSingle();
      if (!existing) {
        await db.from("course_enrollments").insert({ course_id: payment.item_id, student_id: payment.user_id, payment_id: payment.id });
      } else {
        await db.from("course_enrollments").update({ payment_id: payment.id }).eq("id", existing.id);
      }
    } else {
      const { data: session } = await db.from("live_sessions").select("teacher_id, title, subject, session_type").eq("id", payment.item_id).single();
      teacherId = session?.teacher_id ?? null;
      notifTitle = session?.title ?? session?.subject ?? "une session";
      notifLink = `/sessions/book/${payment.item_id}`;

      const mode = session?.session_type === "group" ? "group" : "solo";
      const { data: existing } = await db
        .from("session_bookings")
        .select("id")
        .eq("session_id", payment.item_id)
        .eq("student_id", payment.user_id)
        .maybeSingle();
      if (!existing) {
        await db.from("session_bookings").insert({ session_id: payment.item_id, student_id: payment.user_id, status: "booked", mode, payment_id: payment.id });
      } else {
        await db.from("session_bookings").update({ status: "booked", payment_id: payment.id }).eq("id", existing.id);
      }
    }

    if (teacherId) {
      const platformFee = Math.round(payment.amount * (PLATFORM_FEE_PCT / 100));
      const netAmount = payment.amount - platformFee;
      await db.from("teacher_earnings").insert({
        payment_id: payment.id,
        teacher_id: teacherId,
        amount: payment.amount,
        platform_fee: platformFee,
        net_amount: netAmount,
        status: "pending",
      });
      await db.from("notifications").insert({
        user_id: teacherId,
        type: "payment_received",
        title: "Nouvelle vente",
        body: `Un élève vient d'acheter "${notifTitle}" (${netAmount} DA après commission).`,
        link: notifLink,
      });
    }

    await db.from("notifications").insert({
      user_id: payment.user_id,
      type: "payment_confirmed",
      title: "Paiement confirmé",
      body: `Ton paiement pour "${notifTitle}" a été validé.`,
      link: notifLink,
    });

    return jsonResponse({ ok: true });
  } catch (err) {
    console.error("[chargily-webhook]", err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur inconnue." }, 500);
  }
});
