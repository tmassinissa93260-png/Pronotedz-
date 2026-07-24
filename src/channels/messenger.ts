import { Router } from "express";
import { config } from "../config";
import { handleMessage } from "../agent/agent";

export const messengerRouter = Router();

// Verification du webhook (Facebook Messenger + Instagram DM utilisent la meme plateforme Meta).
messengerRouter.get("/webhooks/messenger", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === config.messenger.verifyToken) {
    res.status(200).send(challenge);
  } else {
    res.sendStatus(403);
  }
});

// Reception des messages entrants (Messenger "page" et Instagram "instagram" partagent ce format).
messengerRouter.post("/webhooks/messenger", async (req, res) => {
  res.sendStatus(200);

  try {
    if (req.body?.object !== "page" && req.body?.object !== "instagram") return;

    for (const entry of req.body.entry || []) {
      const pageId = entry.id as string;
      const businessId = config.messenger.businessMap[pageId];
      if (!businessId) {
        console.warn("Messenger/Instagram: aucun business associe a la page", pageId);
        continue;
      }
      for (const event of entry.messaging || []) {
        const senderId = event.sender?.id as string;
        const text = event.message?.text as string | undefined;
        if (!text || event.message?.is_echo) continue;
        const reply = await handleMessage("messenger", senderId, businessId, text);
        await sendMessengerMessage(senderId, reply);
      }
    }
  } catch (err) {
    console.error("Erreur traitement webhook Messenger/Instagram:", err);
  }
});

export async function sendMessengerMessage(recipientId: string, text: string): Promise<void> {
  if (!config.messenger.pageAccessToken) {
    console.warn("MESSENGER_PAGE_ACCESS_TOKEN manquant: message non envoye (mode simulation).", { recipientId, text });
    return;
  }
  const url = `https://graph.facebook.com/${config.messenger.apiVersion}/me/messages?access_token=${encodeURIComponent(
    config.messenger.pageAccessToken
  )}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recipient: { id: recipientId }, message: { text } }),
  });
  if (!res.ok) {
    console.error("Echec envoi Messenger/Instagram:", res.status, await res.text());
  }
}
