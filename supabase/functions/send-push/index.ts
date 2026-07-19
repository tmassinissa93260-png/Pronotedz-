// Supabase Edge Function: send-push
//
// Sends a real Web Push notification to every device a user has registered
// in push_subscriptions. Two ways to call it:
//   { notificationId }               -> loads title/body/link from that row
//   { userId, title, body, link? }   -> sends an ad-hoc push directly
//
// Intended trigger: a Database Webhook on notifications INSERT (Dashboard ->
// Database -> Webhooks -> new webhook, table "notifications", event
// "Insert", type "HTTP request" to this function's URL, body
// {"notificationId": "{{record.id}}"}). Any code path that inserts a row
// into `notifications` — task reminders, moderation, referrals, etc. —
// then gets push delivery for free with no further wiring.
//
// Required secrets:
//   VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY - generate once with
//     `npx web-push generate-vapid-keys`, keep the same pair forever (the
//     public half also goes in the client as VITE_VAPID_PUBLIC_KEY).
//   VAPID_SUBJECT - a mailto: or https: URL, required by the push spec.
//   PUSH_WEBHOOK_SECRET - if calling this directly (not via a Database
//     Webhook, which doesn't support custom headers here), pass it as
//     `x-webhook-secret`. Optional: only enforced if the secret is set.
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are provided automatically.
//
// Deploy: `supabase functions deploy send-push --no-verify-jwt`

import { createClient } from "jsr:@supabase/supabase-js@2";
import webpush from "npm:web-push@3.6.7";

const VAPID_PUBLIC_KEY = Deno.env.get("VAPID_PUBLIC_KEY") ?? "";
const VAPID_PRIVATE_KEY = Deno.env.get("VAPID_PRIVATE_KEY") ?? "";
const VAPID_SUBJECT = Deno.env.get("VAPID_SUBJECT") ?? "mailto:contact@estadi.dz";
const WEBHOOK_SECRET = Deno.env.get("PUSH_WEBHOOK_SECRET") ?? "";

if (VAPID_PUBLIC_KEY && VAPID_PRIVATE_KEY) {
  webpush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

Deno.serve(async (req) => {
  try {
    if (WEBHOOK_SECRET && req.headers.get("x-webhook-secret") !== WEBHOOK_SECRET) {
      return jsonResponse({ error: "Non autorisé." }, 401);
    }
    if (!VAPID_PUBLIC_KEY || !VAPID_PRIVATE_KEY) {
      return jsonResponse({ error: "VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY ne sont pas configurées." }, 500);
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const db = createClient(supabaseUrl, serviceRoleKey);

    const body = await req.json();

    let userId: string;
    let title: string;
    let pushBody: string;
    let link: string | null;

    if (body.notificationId) {
      const { data: notif, error } = await db
        .from("notifications")
        .select("user_id, title, body, link")
        .eq("id", body.notificationId)
        .single();
      if (error || !notif) return jsonResponse({ error: "Notification introuvable." }, 404);
      userId = notif.user_id;
      title = notif.title;
      pushBody = notif.body ?? "";
      link = notif.link;
    } else if (body.userId && body.title) {
      userId = body.userId;
      title = body.title;
      pushBody = body.body ?? "";
      link = body.link ?? null;
    } else {
      return jsonResponse({ error: "notificationId ou (userId + title) requis." }, 400);
    }

    const { data: subs, error: subsError } = await db
      .from("push_subscriptions")
      .select("id, endpoint, p256dh, auth_key")
      .eq("user_id", userId);
    if (subsError) throw subsError;
    if (!subs || subs.length === 0) return jsonResponse({ sent: 0 });

    const payload = JSON.stringify({ title, body: pushBody, link: link ?? "/dashboard" });

    let sent = 0;
    for (const sub of subs) {
      try {
        await webpush.sendNotification(
          { endpoint: sub.endpoint, keys: { p256dh: sub.p256dh, auth: sub.auth_key } },
          payload,
        );
        sent++;
      } catch (err) {
        const status = (err as { statusCode?: number }).statusCode;
        if (status === 404 || status === 410) {
          // Subscription is gone (browser unsubscribed, device reset, etc.) — prune it.
          await db.from("push_subscriptions").delete().eq("id", sub.id);
        } else {
          console.error("[send-push] delivery failed", status, err);
        }
      }
    }

    return jsonResponse({ sent });
  } catch (err) {
    console.error("[send-push]", err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur inconnue." }, 500);
  }
});
