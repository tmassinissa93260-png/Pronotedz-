// Supabase Edge Function: curriculum-ai
//
// Generates curriculum content on demand — never in bulk, per the product's
// cost discipline. Two actions:
//   { action: "plan", chapterId }                 -> breaks a chapter into leçons
//   { action: "content", lessonId, simplify? }     -> writes/rewrites one leçon
//
// Required secrets (set with `supabase secrets set NAME=value`):
//   AI_API_KEY        - API key for an OpenAI-compatible chat completions endpoint
//   AI_BASE_URL        - e.g. https://api.openai.com/v1 (defaults to that)
//   AI_FAST_MODEL       - cheap/fast model for plans, exercises, simplification
//   AI_ADVANCED_MODEL   - stronger model for the first full explanation of a leçon
// SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are provided automatically by the
// platform to every edge function — do not set them yourself.
//
// Deploy: `supabase functions deploy curriculum-ai`

import { createClient } from "jsr:@supabase/supabase-js@2";

const BUDGET_EUR = 100;

const AI_BASE_URL = Deno.env.get("AI_BASE_URL") ?? "https://api.openai.com/v1";
const AI_API_KEY = Deno.env.get("AI_API_KEY") ?? "";
const AI_FAST_MODEL = Deno.env.get("AI_FAST_MODEL") ?? "gpt-4o-mini";
const AI_ADVANCED_MODEL = Deno.env.get("AI_ADVANCED_MODEL") ?? "gpt-4o";

// Rough $/1M tokens by model family, used only to keep the monthly budget
// counter honest — update if you change providers or the providers' pricing.
const PRICE_PER_MILLION_TOKENS: Record<string, { input: number; output: number }> = {
  default_fast: { input: 0.3, output: 1.2 },
  default_advanced: { input: 3, output: 15 },
};

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

type ChatMessage = { role: "system" | "user"; content: string };

async function callAi(model: string, messages: ChatMessage[], mode: "fast" | "advanced") {
  const res = await fetch(`${AI_BASE_URL}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${AI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.4,
      response_format: { type: "json_object" },
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`AI provider error (${res.status}): ${text.slice(0, 300)}`);
  }
  const data = await res.json();
  const content = data.choices?.[0]?.message?.content;
  if (!content) throw new Error("AI provider returned no content.");
  const usage = data.usage ?? { prompt_tokens: 0, completion_tokens: 0 };
  const price = PRICE_PER_MILLION_TOKENS[mode === "fast" ? "default_fast" : "default_advanced"];
  const costEur =
    (usage.prompt_tokens / 1_000_000) * price.input + (usage.completion_tokens / 1_000_000) * price.output;
  return {
    parsed: JSON.parse(content),
    inputTokens: usage.prompt_tokens as number,
    outputTokens: usage.completion_tokens as number,
    costEur,
  };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    if (!AI_API_KEY) {
      return jsonResponse({ error: "AI_API_KEY n'est pas configurée sur ce projet Supabase." }, 500);
    }

    const authHeader = req.headers.get("Authorization") ?? "";
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    // User-scoped client: only used to verify who is calling.
    const userClient = createClient(supabaseUrl, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: userData, error: userError } = await userClient.auth.getUser();
    if (userError || !userData.user) {
      return jsonResponse({ error: "Authentification requise." }, 401);
    }
    const userId = userData.user.id;

    // Service-role client: bypasses RLS for the actual reads/writes below.
    const db = createClient(supabaseUrl, serviceRoleKey);

    // Monthly cost cap — matches the product's "plafond de coût mensuel".
    const startOfMonth = new Date(Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), 1)).toISOString();
    const { data: usageRows } = await db
      .from("ai_usage")
      .select("cost_eur")
      .gte("created_at", startOfMonth);
    const monthTotal = (usageRows ?? []).reduce((sum, r) => sum + Number(r.cost_eur ?? 0), 0);
    if (monthTotal >= BUDGET_EUR) {
      return jsonResponse({ error: "Le budget IA mensuel de la plateforme est atteint. Réessaie plus tard." }, 429);
    }

    const body = await req.json();

    async function logUsage(mode: string, model: string, r: { inputTokens: number; outputTokens: number; costEur: number }) {
      await db.from("ai_usage").insert({
        user_id: userId,
        mode,
        model,
        input_tokens: r.inputTokens,
        output_tokens: r.outputTokens,
        cost_eur: r.costEur,
      });
    }

    if (body.action === "plan") {
      const chapterId = body.chapterId as string;
      const { data: chapter, error: chapterError } = await db
        .from("edu_chapters")
        .select("id, title_fr, title_ar, summary_fr, trimester, subject_id, edu_subjects(name_fr, edu_levels(label_fr, cycle, grade, track))")
        .eq("id", chapterId)
        .single();
      if (chapterError || !chapter) return jsonResponse({ error: "Chapitre introuvable." }, 404);

      const subject = chapter.edu_subjects as unknown as { name_fr: string; edu_levels: { label_fr: string } } | null;
      const levelLabel = subject?.edu_levels?.label_fr ?? "";

      const result = await callAi(
        AI_FAST_MODEL,
        [
          {
            role: "system",
            content:
              "Tu es un concepteur pédagogique du programme officiel algérien. Réponds uniquement en JSON valide de la forme " +
              '{"lessons":[{"title_fr":"...","title_ar":"..."}]}. Propose 3 à 6 leçons, dans l\'ordre du programme, qui découpent le chapitre. Titres courts et précis.',
          },
          {
            role: "user",
            content: `Niveau: ${levelLabel}\nMatière: ${subject?.name_fr ?? ""}\nChapitre: ${chapter.title_fr}\nRésumé: ${chapter.summary_fr ?? "(aucun)"}`,
          },
        ],
        "fast",
      );
      await logUsage("curriculum_plan", AI_FAST_MODEL, result);

      const lessons = (result.parsed.lessons as { title_fr: string; title_ar: string }[]) ?? [];
      if (lessons.length === 0) return jsonResponse({ error: "L'IA n'a proposé aucune leçon." }, 502);

      const rows = lessons.map((l, i) => ({
        chapter_id: chapterId,
        title_fr: l.title_fr,
        title_ar: l.title_ar,
        order_index: i,
      }));
      const { data: inserted, error: insertError } = await db.from("edu_lessons").insert(rows).select("*");
      if (insertError) return jsonResponse({ error: insertError.message }, 500);

      return jsonResponse({ lessons: inserted });
    }

    if (body.action === "content") {
      const lessonId = body.lessonId as string;
      const simplify = Boolean(body.simplify);

      const { data: lesson, error: lessonError } = await db
        .from("edu_lessons")
        .select(
          "id, title_fr, title_ar, lesson_content, chapter_id, edu_chapters(title_fr, subject_id, edu_subjects(name_fr, edu_levels(label_fr)))",
        )
        .eq("id", lessonId)
        .single();
      if (lessonError || !lesson) return jsonResponse({ error: "Leçon introuvable." }, 404);

      const chapter = lesson.edu_chapters as unknown as {
        title_fr: string;
        edu_subjects: { name_fr: string; edu_levels: { label_fr: string } } | null;
      } | null;
      const subjectName = chapter?.edu_subjects?.name_fr ?? "";
      const levelLabel = chapter?.edu_subjects?.edu_levels?.label_fr ?? "";
      const context = `Niveau: ${levelLabel}\nMatière: ${subjectName}\nChapitre: ${chapter?.title_fr ?? ""}\nLeçon: ${lesson.title_fr}`;

      if (simplify) {
        const existing = lesson.lesson_content as { explanation?: string } | null;
        const result = await callAi(
          AI_FAST_MODEL,
          [
            {
              role: "system",
              content:
                'Tu es un tuteur patient pour élèves algériens (BEM/BAC). Réponds en JSON: {"simplified":"..."}. ' +
                "Réexplique le texte donné avec des mots beaucoup plus simples, des exemples concrets, des phrases courtes.",
            },
            { role: "user", content: `${context}\n\nExplication actuelle:\n${existing?.explanation ?? ""}` },
          ],
          "fast",
        );
        await logUsage("curriculum_simplify", AI_FAST_MODEL, result);

        const merged = { ...(lesson.lesson_content as object), simplified: result.parsed.simplified };
        const { data: updated, error } = await db
          .from("edu_lessons")
          .update({ lesson_content: merged })
          .eq("id", lessonId)
          .select("*")
          .single();
        if (error) return jsonResponse({ error: error.message }, 500);
        return jsonResponse({ lesson: updated });
      }

      const result = await callAi(
        AI_ADVANCED_MODEL,
        [
          {
            role: "system",
            content:
              "Tu es un professeur du programme officiel algérien (BEM/BAC), rigoureux et clair. Réponds uniquement en JSON valide de la forme " +
              '{"explanation":"...", "key_points":["...","..."], "exercises":[{"question":"...","correction":"...","difficulty":"facile|moyen|difficile"}], "sujet":{"statement":"...","correction":"..."}}. ' +
              "L'explication doit suivre exactement le programme algérien pour ce niveau. Propose 3 exercices progressifs et 1 sujet type examen avec sa correction complète.",
          },
          { role: "user", content: context },
        ],
        "advanced",
      );
      await logUsage("curriculum_content", AI_ADVANCED_MODEL, result);

      const { data: updated, error } = await db
        .from("edu_lessons")
        .update({
          lesson_content: { explanation: result.parsed.explanation, key_points: result.parsed.key_points ?? [] },
          exercises: result.parsed.exercises ?? [],
          sujet: result.parsed.sujet ?? null,
          ai_generated_at: new Date().toISOString(),
          ai_model: AI_ADVANCED_MODEL,
        })
        .eq("id", lessonId)
        .select("*")
        .single();
      if (error) return jsonResponse({ error: error.message }, 500);
      return jsonResponse({ lesson: updated });
    }

    return jsonResponse({ error: "Action inconnue." }, 400);
  } catch (err) {
    console.error("[curriculum-ai]", err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur inconnue." }, 500);
  }
});
