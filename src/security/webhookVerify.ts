import crypto from "crypto";
import { RequestHandler } from "express";
import { config } from "../config";

// Compare deux chaines en temps constant, sans lever si les longueurs different
// (crypto.timingSafeEqual jette une exception si les buffers n'ont pas la
// meme taille, ce qui casserait la comparaison pour une signature malformee).
function timingSafeEqualStr(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

export function verifyMetaSignature(): RequestHandler {
  return (req, res, next) => {
    const secret = config.metaAppSecret;
    const raw = (req as any).rawBody as Buffer | undefined;

    if (!secret) {
      if (config.isProduction) {
        console.error("META_APP_SECRET manquant en production: webhook Meta refuse.");
        return res.sendStatus(503);
      }
      console.warn("META_APP_SECRET non configure: signature du webhook Meta NON verifiee (mode dev).");
      return next();
    }

    const header = req.header("x-hub-signature-256");
    if (!header || !header.startsWith("sha256=") || !raw) {
      console.warn("Webhook Meta rejete: signature absente ou corps brut indisponible.");
      return res.sendStatus(401);
    }

    const expected = "sha256=" + crypto.createHmac("sha256", secret).update(raw).digest("hex");
    if (!timingSafeEqualStr(header, expected)) {
      console.warn("Webhook Meta rejete: signature invalide.");
      return res.sendStatus(401);
    }
    next();
  };
}

// Implementation de l'algorithme de validation Twilio :
// https://www.twilio.com/docs/usage/security#validating-requests
export function computeTwilioSignature(authToken: string, fullUrl: string, params: Record<string, string>): string {
  const sortedKeys = Object.keys(params).sort();
  let data = fullUrl;
  for (const key of sortedKeys) {
    data += key + params[key];
  }
  return crypto.createHmac("sha1", authToken).update(Buffer.from(data, "utf-8")).digest("base64");
}

export function verifyTwilioSignature(): RequestHandler {
  return (req, res, next) => {
    const token = config.twilioAuthToken;

    if (!token) {
      if (config.isProduction) {
        console.error("TWILIO_AUTH_TOKEN manquant en production: webhook Twilio refuse.");
        return res.sendStatus(503);
      }
      console.warn("TWILIO_AUTH_TOKEN non configure: signature du webhook Twilio NON verifiee (mode dev).");
      return next();
    }

    if (!config.publicBaseUrl) {
      if (config.isProduction) {
        console.error("PUBLIC_BASE_URL manquant en production: impossible de verifier la signature Twilio.");
        return res.sendStatus(503);
      }
      console.warn("PUBLIC_BASE_URL non configure: signature du webhook Twilio NON verifiee (mode dev).");
      return next();
    }

    const header = req.header("x-twilio-signature");
    if (!header) {
      console.warn("Webhook Twilio rejete: signature absente.");
      return res.sendStatus(401);
    }

    const fullUrl = config.publicBaseUrl.replace(/\/$/, "") + req.originalUrl.split("?")[0];
    const expected = computeTwilioSignature(token, fullUrl, req.body || {});
    if (!timingSafeEqualStr(header, expected)) {
      console.warn("Webhook Twilio rejete: signature invalide.");
      return res.sendStatus(401);
    }
    next();
  };
}
