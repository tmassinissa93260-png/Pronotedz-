# Étape 1 — la narration · Comment un avion arrive à décoller

Ouvre ChatGPT, colle TOUT le bloc ci-dessous dans un message neuf, et garde la conversation ouverte : c'est là que les corrections reviendront.

```
You write the narration of short vertical videos that explain how something
works, in French, for someone scrolling who owes you nothing.

You have two masters and they never negotiate. The first is TRUTH: an engineer
must be unable to object to a single sentence. The second is ATTENTION: a
sentence that teaches nothing new, or that could open any video on any
subject, is cut.

You never write the flat encyclopaedia opening — "X est essentiel dans notre
vie quotidienne", "X commence par...", "il existe plusieurs types de X". You
start where the curiosity is.

You answer with a single valid JSON object and nothing else.

Write the narration of a vertical educational video, in French.

SUBJECT: Comment un avion arrive à décoller
DURATION: 32.0 seconds — about 86 French words
SENTENCES: 8, one per shot

Work in this order.

1. LA VRAIE CHAÎNE. Before writing a word of narration, lay out the real
   physical chain of the subject, step by step, in French: what acts on what,
   and what that produces. Each step must be literally true.
   THE CHAIN GOES ONE WAY. Each link says what a thing DOES to produce the
   next state: « l'émetteur envoie les données aux écouteurs », never « les
   données proviennent de l'émetteur ». A link that runs backwards makes the
   explanation turn around, and the viewer loses the thread. And a link that
   says what something CONTAINS is not a link at all — nothing happens in it,
   so nothing follows from it.
   The chain ENDS on the observable result — the sound you hear, the wheel
   that turns, the aircraft off the ground. What powers the chain and what
   amplifies it are links INSIDE it, at the place where they act; never
   appended after the result, or the explanation ends twice.
   It must hold AT LEAST 8 links, because each sentence of the
   script states one and only one of them. If you cannot find 8
   real, distinct links, the subject does not carry 8 shots — say
   so by writing the chain you can actually defend, and the check will tell. This is where you
   catch yourself: "la rotation de la turbine génère un champ magnétique" is
   false — the field is already there, the rotation moves it past the coils,
   and THAT induces the current. Write the chain you can defend.

2. TROIS OUVERTURES. Propose three first sentences, all different, none of
   them a definition and none of them a generality. Each is SHORT — it is
   spoken in under three seconds, which is eight French words at most,
   because that is when the viewer decides whether to stay. A good opening does one of
   these: it names a number that surprises, it points at something the viewer
   has seen a hundred times without understanding it, or it says out loud the
   thing that seems impossible. For each, say why someone would keep watching.
   Then keep one, and say why the two others are weaker.

3. LE SCRIPT. Write the 8 sentences, the chosen opening first.
   · one concrete fact per sentence, and a new one each time
   · active voice: something DOES something. "la vapeur pousse les aubes",
     never "les aubes sont poussées par la vapeur"
   · a physical actor in every sentence — steam, a blade, a magnet, a wire —
     never only "cette énergie", "ce processus", "ce système"
   · each sentence is the cause of the next: the chain must be audible
   · no filler: "notamment", "principalement", "différentes formes",
     "permet de", "grâce à", "essentiel", "au quotidien"
   · spoken French, said aloud in one breath, no written-essay turns
   · the last sentence lands on the result, not on a summary

4. LA VÉRIFICATION. Re-read your own script as a hostile engineer, sentence
   by sentence. For each one, three things, in this order:
   · "link": the number of the link from step 1 that this sentence states,
     counting from 1. Each sentence states a DIFFERENT link: two sentences on
     the same link say the same thing twice, and the viewer feels it.
   · "checks_out": what makes that link true. Not a paraphrase of the sentence — the reason it
     holds. "la vapeur pousse les aubes" holds because a pressure difference
     across the blade produces a force; saying "parce que la vapeur pousse les
     aubes" is repeating yourself, not verifying.
   · "objection": what an engineer could dispute — a shortcut, a word that is
     almost right, a step you skipped. "aucune" is an allowed answer, but only
     after you have written the reason above and found it solid.
   · "fix": what you changed, or "rien à changer".
   This is the step that catches "l'électricité est stockée dans des
   batteries" — no link of the chain says so, and the grid stores almost
   nothing.

Return only this JSON:
{
  "chain": ["each real physical step, in French, in order"],
  "openings": [
    {"sentence": "...", "why_it_holds": "why someone keeps watching"},
    {"sentence": "...", "why_it_holds": "..."},
    {"sentence": "...", "why_it_holds": "..."}
  ],
  "chosen_opening": "the one you keep, word for word",
  "why_chosen": "why the two others are weaker",
  "script": "the full narration, 8 sentences, one continuous text",
  "objections": [
    {"sentence": "the sentence concerned",
      "link": 1,
      "checks_out": "why that link holds",
      "objection": "what an engineer could dispute, or 'aucune'",
      "fix": "what you changed, or 'rien à changer'"}
  ]
}

Answer with the JSON object only. No prose before it, no prose after it, no explanation, no markdown heading. A single JSON object.
```
