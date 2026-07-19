// Supabase Edge Function: group-quiz-ai
//
// Generates an AI quiz + revision checklist for a study group's upcoming
// exam and stores it as a group_exam_alerts row. Called once per alert
// (not regenerated automatically) to respect the platform's AI cost cap.
//
// Body: { groupId, subject, chapters: string[], examDate: ISO string }
//
// Required secrets: same as curriculum-ai (AI_API_KEY, AI_BASE_URL,
// AI_FAST_MODEL). SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_ANON_KEY
// are provided automatically.
//
// Deploy: `supabase functions deploy group-quiz-ai`

import { createClient } from "jsr:@supabase/supabase-js@2";

const BUDGET_EUR = 100;

const AI_BASE_URL = Deno.env.get("AI_BASE_URL") ?? "https://api.openai.com/v1";
const AI_API_KEY = Deno.env.get("AI_API_KEY") ?? "";
const AI_FAST_MODEL = Deno.env.get("AI_FAST_MODEL") ?? "gpt-4o-mini";

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
    if (!AI_API_KEY) return jsonResponse({ error: "AI_API_KEY n'est pas configurée sur ce projet Supabase." }, 500);

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
    const groupId = body.groupId as string;
    const subject = (body.subject as string) ?? "";
    const chapters = Array.isArray(body.chapters) ? (body.chapters as string[]) : [];
    const examDate = body.examDate as string;

    const { data: membership } = await db
      .from("group_members")
      .select("user_id")
      .eq("group_id", groupId)
      .eq("user_id", userId)
      .maybeSingle();
    if (!membership) return jsonResponse({ error: "Tu n'es pas membre de ce groupe." }, 403);

    const startOfMonth = new Date(Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), 1)).toISOString();
    const { data: usageRows } = await db.from("ai_usage").select("cost_eur").gte("created_at", startOfMonth);
    const monthTotal = (usageRows ?? []).reduce((sum, r) => sum + Number(r.cost_eur ?? 0), 0);
    if (monthTotal >= BUDGET_EUR) {
      return jsonResponse({ error: "Le budget IA mensuel de la plateforme est atteint. Réessaie plus tard." }, 429);
    }

    const res = await fetch(`${AI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${AI_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: AI_FAST_MODEL,
        temperature: 0.4,
        response_format: { type: "json_object" },
        messages: [
          {
            role: "system",
            content:
              "Tu es un professeur du programme officiel algérien (BEM/BAC). Réponds uniquement en JSON valide de la forme " +
              '{"quiz":[{"question":"...","options":["...","...","...","..."],"correct_index":0,"explanation":"..."}],"checklist":["...","..."]}. ' +
              "Génère 5 questions à choix multiple (4 options chacune) couvrant les chapitres donnés, et une checklist de 5 à 8 actions de révision concrètes avant l'examen.",
          },
          { role: "user", content: `Matière: ${subject}\nChapitres: ${chapters.join(", ") || "(non précisés)"}\nDate d'examen: ${examDate}` },
        ],
      }),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`AI provider error (${res.status}): ${text.slice(0, 300)}`);
    }
    const aiData = await res.json();
    const content = aiData.choices?.[0]?.message?.content;
    if (!content) throw new Error("AI provider returned no content.");
    const parsed = JSON.parse(content);

    const usage = aiData.usage ?? { prompt_tokens: 0, completion_tokens: 0 };
    const costEur = (usage.prompt_tokens / 1_000_000) * 0.3 + (usage.completion_tokens / 1_000_000) * 1.2;
    await db.from("ai_usage").insert({
      user_id: userId,
      mode: "group_quiz",
      model: AI_FAST_MODEL,
      input_tokens: usage.prompt_tokens,
      output_tokens: usage.completion_tokens,
      cost_eur: costEur,
    });

    const { data: inserted, error: insertError } = await db
      .from("group_exam_alerts")
      .insert({
        group_id: groupId,
        created_by: userId,
        subject,
        chapters,
        exam_date: examDate,
        quiz: parsed.quiz ?? [],
        checklist: parsed.checklist ?? [],
      })
      .select("*")
      .single();
    if (insertError) return jsonResponse({ error: insertError.message }, 500);

    return jsonResponse({ id: inserted.id, quiz: inserted.quiz, checklist: inserted.checklist });
  } catch (err) {
    console.error("[group-quiz-ai]", err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur inconnue." }, 500);
  }
});
