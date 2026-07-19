// Supabase Edge Function: tools-ai
//
// Two on-demand tools, same cost-cap discipline as curriculum-ai:
//   { action: "homework", imagePath: string, question?: string }
//     -> vision explanation of a photographed exercise (never persisted —
//        homework help is ephemeral by design, nothing to moderate or cache)
//   { action: "memo", sourceText: string, title: string, subject?: string, level?: string }
//     -> AI study sheet (summary + flashcards), saved to memo_sheets
//
// Required secrets: AI_API_KEY, AI_BASE_URL (optional), AI_FAST_MODEL,
// AI_VISION_MODEL (defaults to AI_ADVANCED_MODEL if unset)
// Deploy: `supabase functions deploy tools-ai`

import { createClient } from "jsr:@supabase/supabase-js@2";

const BUDGET_EUR = 100;
const AI_BASE_URL = Deno.env.get("AI_BASE_URL") ?? "https://api.openai.com/v1";
const AI_API_KEY = Deno.env.get("AI_API_KEY") ?? "";
const AI_FAST_MODEL = Deno.env.get("AI_FAST_MODEL") ?? "gpt-4o-mini";
const AI_VISION_MODEL = Deno.env.get("AI_VISION_MODEL") ?? Deno.env.get("AI_ADVANCED_MODEL") ?? "gpt-4o";

const PRICE_PER_MILLION_TOKENS = { input: 3, output: 15 };

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
    const userClient = createClient(supabaseUrl, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: userData, error: userError } = await userClient.auth.getUser();
    if (userError || !userData.user) return jsonResponse({ error: "Authentification requise." }, 401);
    const userId = userData.user.id;

    const db = createClient(supabaseUrl, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

    const startOfMonth = new Date(Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), 1)).toISOString();
    const { data: usageRows } = await db.from("ai_usage").select("cost_eur").gte("created_at", startOfMonth);
    const monthTotal = (usageRows ?? []).reduce((s, r) => s + Number(r.cost_eur ?? 0), 0);
    if (monthTotal >= BUDGET_EUR) {
      return jsonResponse({ error: "Le budget IA mensuel de la plateforme est atteint. Réessaie plus tard." }, 429);
    }

    const body = await req.json();

    async function logUsage(mode: string, model: string, inputTokens: number, outputTokens: number, costEur: number) {
      await db.from("ai_usage").insert({ user_id: userId, mode, model, input_tokens: inputTokens, output_tokens: outputTokens, cost_eur: costEur });
    }

    if (body.action === "homework") {
      const { data: signed, error: signError } = await db.storage
        .from("ai-uploads")
        .createSignedUrl(body.imagePath as string, 600);
      if (signError || !signed) return jsonResponse({ error: "Impossible d'accéder à la photo." }, 400);

      const res = await fetch(`${AI_BASE_URL}/chat/completions`, {
        method: "POST",
        headers: { Authorization: `Bearer ${AI_API_KEY}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: AI_VISION_MODEL,
          messages: [
            {
              role: "system",
              content:
                'Tu es un tuteur pour élèves algériens (BEM/BAC). On te montre la photo d\'un exercice. Réponds en JSON: {"explanation":"...", "steps":["...","..."], "answer":"..."}. ' +
                "Explique la méthode pas à pas avant de donner la réponse finale, dans la langue de l'énoncé (français ou arabe).",
            },
            {
              role: "user",
              content: [
                { type: "text", text: body.question || "Explique-moi cet exercice." },
                { type: "image_url", image_url: { url: signed.signedUrl } },
              ],
            },
          ],
          response_format: { type: "json_object" },
        }),
      });
      if (!res.ok) {
        console.error("[tools-ai] homework failed", res.status, await res.text());
        return jsonResponse({ error: "Impossible d'analyser cette photo pour le moment." }, 502);
      }
      const data = await res.json();
      const usage = data.usage ?? { prompt_tokens: 0, completion_tokens: 0 };
      const costEur =
        (usage.prompt_tokens / 1_000_000) * PRICE_PER_MILLION_TOKENS.input +
        (usage.completion_tokens / 1_000_000) * PRICE_PER_MILLION_TOKENS.output;
      await logUsage("homework_help", AI_VISION_MODEL, usage.prompt_tokens, usage.completion_tokens, costEur);

      const parsed = JSON.parse(data.choices[0].message.content);
      return jsonResponse({ result: parsed });
    }

    if (body.action === "memo") {
      const res = await fetch(`${AI_BASE_URL}/chat/completions`, {
        method: "POST",
        headers: { Authorization: `Bearer ${AI_API_KEY}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: AI_FAST_MODEL,
          messages: [
            {
              role: "system",
              content:
                'Tu transformes un texte de cours en fiche de révision. Réponds en JSON: {"blocks":[{"type":"summary","content":"..."},{"type":"flashcard","front":"...","back":"..."}]}. ' +
                "Produis 1 bloc résumé puis 5 à 10 flashcards question/réponse couvrant les points clés.",
            },
            { role: "user", content: (body.sourceText as string).slice(0, 8000) },
          ],
          response_format: { type: "json_object" },
        }),
      });
      if (!res.ok) {
        console.error("[tools-ai] memo failed", res.status, await res.text());
        return jsonResponse({ error: "Impossible de générer cette fiche pour le moment." }, 502);
      }
      const data = await res.json();
      const usage = data.usage ?? { prompt_tokens: 0, completion_tokens: 0 };
      const costEur =
        (usage.prompt_tokens / 1_000_000) * 0.3 + (usage.completion_tokens / 1_000_000) * 1.2;
      await logUsage("memo_generation", AI_FAST_MODEL, usage.prompt_tokens, usage.completion_tokens, costEur);

      const parsed = JSON.parse(data.choices[0].message.content);
      const { data: sheet, error } = await db
        .from("memo_sheets")
        .insert({
          student_id: userId,
          title: body.title,
          subject: body.subject ?? null,
          level: body.level ?? null,
          chapter: null,
          source_kind: "text",
          source_text: (body.sourceText as string).slice(0, 8000),
          blocks: parsed.blocks ?? [],
          formats: { available: ["summary", "flashcards"] },
        })
        .select("*")
        .single();
      if (error) return jsonResponse({ error: error.message }, 500);
      return jsonResponse({ sheet });
    }

    return jsonResponse({ error: "Action inconnue." }, 400);
  } catch (err) {
    console.error("[tools-ai]", err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur inconnue." }, 500);
  }
});
