import { Router } from "express";
import { config } from "../config";
import { handleMessage } from "../agent/agent";

// Integration Twilio Voice : Twilio gere lui-meme la telephonie, la
// reconnaissance vocale (speech-to-text) via <Gather input="speech"> et la
// synthese vocale (text-to-speech) via <Say>. On ne fait que generer du TwiML.
export const voiceRouter = Router();

function escapeXml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function gatherTwiml(prompt: string, gatherActionUrl: string): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" language="fr-FR" speechTimeout="auto" action="${gatherActionUrl}" method="POST">
    <Say language="fr-FR">${escapeXml(prompt)}</Say>
  </Gather>
  <Say language="fr-FR">Nous n'avons rien entendu, au revoir.</Say>
  <Hangup/>
</Response>`;
}

function hangupTwiml(prompt: string): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="fr-FR">${escapeXml(prompt)}</Say>
  <Hangup/>
</Response>`;
}

// Premier appel entrant : Twilio POST ici (a configurer dans "A call comes in" sur le numero Twilio).
voiceRouter.post("/webhooks/voice/incoming", (req, res) => {
  const to = req.body?.To as string;
  const businessId = config.voice.businessMap[to];
  res.type("text/xml");

  if (!businessId) {
    console.warn("Voix: aucun business associe au numero Twilio", to);
    res.send(hangupTwiml("Ce numero n'est pas encore configure. Au revoir."));
    return;
  }

  res.send(gatherTwiml("Bonjour, bienvenue. Comment puis-je vous aider ?", "/webhooks/voice/gather"));
});

// Reponse a chaque tour de parole : Twilio transcrit la voix et poste le texte dans SpeechResult.
voiceRouter.post("/webhooks/voice/gather", async (req, res) => {
  res.type("text/xml");
  try {
    const to = req.body?.To as string;
    const callSid = req.body?.CallSid as string;
    const speechResult = req.body?.SpeechResult as string | undefined;
    const businessId = config.voice.businessMap[to];

    if (!businessId) {
      res.send(hangupTwiml("Ce numero n'est pas encore configure. Au revoir."));
      return;
    }
    if (!speechResult) {
      res.send(hangupTwiml("Je n'ai pas compris, au revoir."));
      return;
    }

    const reply = await handleMessage("voice", callSid, businessId, speechResult);
    const lower = speechResult.toLowerCase();
    const wantsToEnd = /au revoir|merci.*au revoir|c'est tout|rien d'autre|non merci/.test(lower);

    if (wantsToEnd) {
      res.send(hangupTwiml(reply));
    } else {
      res.send(gatherTwiml(reply, "/webhooks/voice/gather"));
    }
  } catch (err) {
    console.error("Erreur traitement webhook Voix:", err);
    res.send(hangupTwiml("Une erreur est survenue, veuillez rappeler plus tard."));
  }
});
