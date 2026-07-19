// Supabase Edge Function: live-session-room
//
// Creates (or reuses) the Daily.co room for a live session, and enforces who
// may join and when — room creation needs a secret API key so it can't live
// on the client.
//
// Body: { sessionId: string }
// Required secret: DAILY_API_KEY (set with `supabase secrets set DAILY_API_KEY=...`)
// Deploy: `supabase functions deploy live-session-room`

import { createClient } from "jsr:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

const JOIN_WINDOW_MIN = 15;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const dailyApiKey = Deno.env.get("DAILY_API_KEY");
    if (!dailyApiKey) return jsonResponse({ error: "Configuration visio manquante (DAILY_API_KEY)." }, 500);

    const authHeader = req.headers.get("Authorization") ?? "";
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const userClient = createClient(supabaseUrl, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: userData, error: userError } = await userClient.auth.getUser();
    if (userError || !userData.user) return jsonResponse({ error: "Authentification requise." }, 401);
    const userId = userData.user.id;

    const db = createClient(supabaseUrl, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

    const { sessionId } = await req.json();
    const { data: session, error: sessionError } = await db
      .from("live_sessions")
      .select("id, teacher_id, scheduled_at, duration_min, daily_room_url, allow_recording")
      .eq("id", sessionId)
      .maybeSingle();
    if (sessionError || !session) return jsonResponse({ error: "Session introuvable." }, 404);

    const isTeacher = session.teacher_id === userId;
    if (!isTeacher) {
      const { data: booking } = await db
        .from("session_bookings")
        .select("id")
        .eq("session_id", session.id)
        .eq("student_id", userId)
        .in("status", ["booked", "attended"])
        .maybeSingle();
      if (!booking) return jsonResponse({ error: "Tu n'es pas inscrit à cette session." }, 403);
    }

    const start = new Date(session.scheduled_at).getTime();
    const openAt = start - JOIN_WINDOW_MIN * 60 * 1000;
    const now = Date.now();
    if (now < openAt) {
      const mins = Math.ceil((openAt - now) / 60000);
      return jsonResponse({ error: `La salle ouvrira dans ${mins} min.`, opensInMin: mins }, 425);
    }

    if (session.daily_room_url) return jsonResponse({ url: session.daily_room_url });

    const roomName = `estadi-${session.id.slice(0, 8)}-${Date.now().toString(36)}`;
    const exp = Math.floor((start + (session.duration_min + 30) * 60 * 1000) / 1000);

    const res = await fetch("https://api.daily.co/v1/rooms", {
      method: "POST",
      headers: { Authorization: `Bearer ${dailyApiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        name: roomName,
        privacy: "public",
        properties: {
          exp,
          enable_screenshare: true,
          enable_chat: true,
          start_video_off: false,
          start_audio_off: false,
          enable_recording: session.allow_recording ? "cloud" : undefined,
        },
      }),
    });
    if (!res.ok) {
      console.error("[live-session-room] Daily create room failed", res.status, await res.text());
      return jsonResponse({ error: "Impossible de créer la salle visio." }, 502);
    }
    const room = (await res.json()) as { url: string };

    await db.from("live_sessions").update({ daily_room_url: room.url, status: "live" }).eq("id", session.id);

    return jsonResponse({ url: room.url });
  } catch (err) {
    console.error("[live-session-room]", err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur inconnue." }, 500);
  }
});
