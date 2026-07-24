import { Router } from "express";
import { handleMessage } from "../agent/agent";
import { listBusinesses } from "../businesses/store";

export const webchatRouter = Router();

webchatRouter.get("/businesses", (_req, res) => {
  res.json(listBusinesses());
});

webchatRouter.post("/chat", async (req, res) => {
  try {
    const { business_id, session_id, message } = req.body || {};
    if (!business_id || !session_id || !message) {
      return res.status(400).json({ error: "business_id, session_id et message sont requis." });
    }
    const reply = await handleMessage("webchat", String(session_id), String(business_id), String(message));
    res.json({ reply });
  } catch (err: any) {
    console.error("Erreur /api/chat:", err);
    res.status(500).json({ error: err.message || "Erreur interne." });
  }
});
