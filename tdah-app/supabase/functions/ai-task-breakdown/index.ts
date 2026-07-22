// Supabase Edge Function (Deno). Reçoit le titre d'une tâche floue et renvoie
// une décomposition en sous-étapes concrètes via l'API Claude.
//
// La clé API Anthropic ne doit JAMAIS être embarquée dans l'app mobile —
// c'est tout l'intérêt de passer par cette fonction serveur.
//
// Déploiement : supabase functions deploy ai-task-breakdown
// Secret requis : supabase secrets set ANTHROPIC_API_KEY=sk-ant-...

import { createClient } from 'jsr:@supabase/supabase-js@2';

const ANTHROPIC_API_KEY = Deno.env.get('ANTHROPIC_API_KEY');
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')!;

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  // Vérifie que l'appelant est bien un utilisateur authentifié.
  const authHeader = req.headers.get('Authorization');
  if (!authHeader) {
    return new Response(JSON.stringify({ error: 'Non authentifié' }), { status: 401 });
  }

  const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
  });
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return new Response(JSON.stringify({ error: 'Non authentifié' }), { status: 401 });
  }

  const { titre, preferenceTon, granularite } = await req.json();

  if (!titre || typeof titre !== 'string') {
    return new Response(JSON.stringify({ error: '"titre" manquant' }), { status: 400 });
  }

  const tonInstruction =
    {
      direct: 'Ton direct et concis, sans fioritures.',
      doux: 'Ton bienveillant, jamais culpabilisant.',
      humoristique: 'Ton léger, avec une pointe d’humour, sans être lourd.',
    }[preferenceTon as string] ?? 'Ton bienveillant, jamais culpabilisant.';

  // Curseur de granularité façon Goblin Tools ("spiciness") : à surcharge
  // cognitive élevée, on veut des étapes minuscules ; à faible surcharge,
  // une décomposition plus large suffit et évite de noyer l'utilisateur
  // sous une liste à rallonge.
  const granulariteInstruction =
    {
      1: '2 à 3 sous-étapes larges seulement — l’utilisateur a de l’énergie, ne le noie pas de détails.',
      2: '3 à 5 sous-étapes, niveau standard.',
      3: '6 à 10 sous-étapes minuscules, chacune démarrable en moins de 30 secondes de réflexion — l’utilisateur est en surcharge et a besoin du plus petit pas possible.',
    }[Number(granularite) || 2] ?? '3 à 5 sous-étapes, niveau standard.';

  const systemPrompt = `Tu aides une personne adulte avec un TDAH à décomposer une tâche floue en sous-étapes très concrètes et actionnables (chacune formulée comme une action physique précise, pas un objectif abstrait).
Granularité demandée : ${granulariteInstruction}
${tonInstruction}
Ne jamais culpabiliser, ne jamais dire "il suffit de" ou "simplement".
Réponds UNIQUEMENT avec un JSON valide de la forme : {"sous_taches": ["...", "..."]}`;

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': ANTHROPIC_API_KEY!,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-5',
      max_tokens: 512,
      system: systemPrompt,
      messages: [{ role: 'user', content: `Tâche à décomposer : "${titre}"` }],
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    return new Response(JSON.stringify({ error: 'Erreur API Claude', detail: errText }), { status: 502 });
  }

  const data = await response.json();
  const textBlock = data.content?.find((block: { type: string }) => block.type === 'text');

  let sousTaches: string[] = [];
  try {
    sousTaches = JSON.parse(textBlock.text).sous_taches;
  } catch {
    return new Response(JSON.stringify({ error: 'Réponse IA non parsable' }), { status: 502 });
  }

  return new Response(JSON.stringify({ sous_taches: sousTaches }), {
    headers: { 'content-type': 'application/json' },
  });
});
