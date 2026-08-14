import { Router } from "express";
import { config } from "../config";
import { handleMessage } from "../agent/agent";
import { verifyMetaSignature } from "../security/webhookVerify";
import { markEventProcessedOnce } from "../businesses/store";

export const whatsappRouter = Router();

// Verification du webhook (etape obligatoire cote Meta Developer Console).
whatsappRouter.get("/webhooks/whatsapp", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === config.whatsapp.verifyToken) {
    res.status(200).send(challenge);
  } else {
    res.sendStatus(403);
  }
});

// Reception des messages entrants WhatsApp.
whatsappRouter.post("/webhooks/whatsapp", verifyMetaSignature(), async (req, res) => {
  // Repondre tout de suite : Meta attend un 200 rapide, sinon il reessaie/desactive le webhook.
  res.sendStatus(200);

  try {
    const entries = req.body?.entry || [];
    for (const entry of entries) {
      for (const change of entry.changes || []) {
        const value = change.value;
        const phoneNumberId = value?.metadata?.phone_number_id;
        const businessId = phoneNumberId ? config.whatsapp.businessMap[phoneNumberId] : undefined;
        if (!businessId) {
          console.warn("WhatsApp: aucun business associe au phone_number_id", phoneNumberId);
          continue;
        }
        for (const message of value?.messages || []) {
          if (message.type !== "text") continue;
          const messageId = message.id as string | undefined;
          // Meta peut renvoyer le meme evenement (timeout, erreur transitoire) :
          // on ignore silencieusement tout message deja traite.
          if (messageId && !markEventProcessedOnce("whatsapp", messageId)) {
            continue;
          }
          const from = message.from as string;
          const text = message.text?.body as string;
          const reply = await handleMessage("whatsapp", from, businessId, text);
          await sendWhatsappMessage(phoneNumberId, from, reply);
        }
      }
    }
  } catch (err) {
    console.error("Erreur traitement webhook WhatsApp:", err);
  }
});

export async function sendWhatsappMessage(phoneNumberId: string, to: string, body: string): Promise<void> {
  if (!config.whatsapp.accessToken) {
    console.warn(
      `WHATSAPP_ACCESS_TOKEN manquant: message non envoye (mode simulation), destinataire se terminant par ...${to.slice(-4)}, longueur=${body.length}`
    );
    return;
  }
  const url = `https://graph.facebook.com/${config.whatsapp.apiVersion}/${phoneNumberId}/messages`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.whatsapp.accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      to,
      type: "text",
      text: { body },
    }),
  });
  if (!res.ok) {
    console.error("Echec envoi WhatsApp:", res.status, await res.text());
  }
}
