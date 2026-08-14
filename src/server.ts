import "dotenv/config";
import express from "express";
import path from "path";
import { config } from "./config";
import { webchatRouter } from "./channels/webchat";
import { whatsappRouter } from "./channels/whatsapp";
import { messengerRouter } from "./channels/messenger";
import { voiceRouter } from "./channels/voice";
import { seed } from "./businesses/seed";
import { rateLimit } from "./security/rateLimit";

seed();

const app = express();
app.set("trust proxy", true);

// Capture le corps brut de la requete (necessaire pour verifier les signatures
// HMAC des webhooks Meta/Twilio, qui portent sur les octets exacts recus).
const captureRawBody = (req: express.Request, _res: express.Response, buf: Buffer) => {
  (req as any).rawBody = buf;
};
app.use(express.json({ verify: captureRawBody }));
app.use(express.urlencoded({ extended: true, verify: captureRawBody })); // requis pour les webhooks Twilio

app.use(express.static(path.join(__dirname, "..", "public")));

app.use("/api", rateLimit({ windowMs: 60_000, max: 20 }), webchatRouter);
app.use(whatsappRouter);
app.use(messengerRouter);
app.use(voiceRouter);

app.get("/health", (_req, res) => res.json({ ok: true }));

app.listen(config.port, () => {
  console.log(`Agent IA en ecoute sur http://localhost:${config.port}`);
  console.log(`Demo web chat: http://localhost:${config.port}/`);
});
