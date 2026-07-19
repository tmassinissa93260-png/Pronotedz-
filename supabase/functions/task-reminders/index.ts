// Supabase Edge Function: task-reminders
//
// Not user-invoked — meant to be called on a schedule (every 10-15 min) by a
// Supabase Scheduled Trigger / pg_cron job, since it scans ALL students'
// due tasks rather than acting on behalf of one caller.
//
// Two reminder tiers, each fired at most once per task (tracked in
// task_reminder_log so re-running the scan never double-notifies):
//   "due_soon" - reminder_at has passed but due_at has not yet
//   "overdue"  - due_at has passed (within the last 2 days) and the task is
//                still not done
//
// For each match: inserts a row into `notifications` (the same table the
// header bell already reads) — which is enough to show up in-app. If a
// Database Webhook is configured on notifications INSERT -> send-push, the
// student additionally gets a real push notification with no further code
// needed here.
//
// Required secrets:
//   TASK_REMINDER_CRON_SECRET - shared secret; the caller must send it as
//                                the `x-cron-secret` header. Prevents randoms
//                                from spamming every student's notifications.
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are provided automatically.
//
// Deploy: `supabase functions deploy task-reminders --no-verify-jwt`
// (--no-verify-jwt because this is called by a cron job, not a logged-in user)

import { createClient } from "jsr:@supabase/supabase-js@2";

const CRON_SECRET = Deno.env.get("TASK_REMINDER_CRON_SECRET") ?? "";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

Deno.serve(async (req) => {
  try {
    if (!CRON_SECRET || req.headers.get("x-cron-secret") !== CRON_SECRET) {
      return jsonResponse({ error: "Non autorisé." }, 401);
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const db = createClient(supabaseUrl, serviceRoleKey);

    const now = new Date();
    const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000).toISOString();
    const nowIso = now.toISOString();

    let dueSoonCount = 0;
    let overdueCount = 0;

    // Tier "due_soon": reminder_at has passed, due_at hasn't yet.
    {
      const { data: tasks, error } = await db
        .from("student_tasks")
        .select("id, student_id, title, due_at")
        .neq("status", "done")
        .not("reminder_at", "is", null)
        .lte("reminder_at", nowIso)
        .gt("due_at", nowIso);
      if (error) throw error;

      for (const task of tasks ?? []) {
        const { data: already } = await db
          .from("task_reminder_log")
          .select("id")
          .eq("task_id", task.id)
          .eq("tier", "due_soon")
          .maybeSingle();
        if (already) continue;

        await db.from("notifications").insert({
          user_id: task.student_id,
          type: "task_reminder",
          title: "Échéance à venir",
          body: `"${task.title}" est à faire pour le ${new Date(task.due_at!).toLocaleString("fr-DZ", { dateStyle: "medium", timeStyle: "short" })}.`,
          link: "/tasks",
        });
        await db.from("task_reminder_log").insert({ task_id: task.id, student_id: task.student_id, tier: "due_soon", channel: "app" });
        dueSoonCount++;
      }
    }

    // Tier "overdue": due_at has passed (recently), task still not done.
    {
      const { data: tasks, error } = await db
        .from("student_tasks")
        .select("id, student_id, title, due_at")
        .neq("status", "done")
        .not("due_at", "is", null)
        .lte("due_at", nowIso)
        .gte("due_at", twoDaysAgo);
      if (error) throw error;

      for (const task of tasks ?? []) {
        const { data: already } = await db
          .from("task_reminder_log")
          .select("id")
          .eq("task_id", task.id)
          .eq("tier", "overdue")
          .maybeSingle();
        if (already) continue;

        await db.from("notifications").insert({
          user_id: task.student_id,
          type: "task_reminder",
          title: "Tâche en retard",
          body: `"${task.title}" devait être terminée le ${new Date(task.due_at!).toLocaleString("fr-DZ", { dateStyle: "medium", timeStyle: "short" })}.`,
          link: "/tasks",
        });
        await db.from("task_reminder_log").insert({ task_id: task.id, student_id: task.student_id, tier: "overdue", channel: "app" });
        overdueCount++;
      }
    }

    return jsonResponse({ dueSoonCount, overdueCount });
  } catch (err) {
    console.error("[task-reminders]", err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur inconnue." }, 500);
  }
});
