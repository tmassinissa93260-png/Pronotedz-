import "dotenv/config";
import express from "express";
import path from "path";
import { config } from "./config";
import { webchatRouter } from "./channels/webchat";
import { whatsappRouter } from "./channels/whatsapp";
import { messengerRouter } from "./channels/messenger";
import { voiceRouter } from "./channels/voice";
import { seed } from "./businesses/seed";

seed();

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true })); // requis pour les webhooks Twilio (application/x-www-form-urlencoded)

app.use(express.static(path.join(__dirname, "..", "public")));

app.use("/api", webchatRouter);
app.use(whatsappRouter);
app.use(messengerRouter);
app.use(voiceRouter);

app.get("/health", (_req, res) => res.json({ ok: true }));

app.listen(config.port, () => {
  console.log(`Agent IA en ecoute sur http://localhost:${config.port}`);
  console.log(`Demo web chat: http://localhost:${config.port}/`);
});
