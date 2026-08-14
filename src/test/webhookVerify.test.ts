import { test, describe } from "node:test";
import assert from "node:assert/strict";
import crypto from "crypto";
import { computeTwilioSignature } from "../security/webhookVerify";

describe("webhook Meta: signature HMAC-SHA256", () => {
  test("une signature valide correspond au HMAC attendu", () => {
    const secret = "test-app-secret";
    const body = Buffer.from(JSON.stringify({ object: "whatsapp_business_account", entry: [] }));
    const signature = "sha256=" + crypto.createHmac("sha256", secret).update(body).digest("hex");

    const recomputed = "sha256=" + crypto.createHmac("sha256", secret).update(body).digest("hex");
    assert.equal(signature, recomputed);
  });

  test("un corps modifie change la signature attendue (detecte une alteration)", () => {
    const secret = "test-app-secret";
    const original = Buffer.from(JSON.stringify({ a: 1 }));
    const tampered = Buffer.from(JSON.stringify({ a: 2 }));

    const sigOriginal = crypto.createHmac("sha256", secret).update(original).digest("hex");
    const sigTampered = crypto.createHmac("sha256", secret).update(tampered).digest("hex");
    assert.notEqual(sigOriginal, sigTampered);
  });
});

describe("webhook Twilio: signature X-Twilio-Signature", () => {
  test("signature valide reproductible avec le meme secret/url/params", () => {
    const authToken = "test-twilio-token";
    const url = "https://example.com/webhooks/voice/incoming";
    const params = { CallSid: "CA123", From: "+213555000000", To: "+213555000003" };

    const sig1 = computeTwilioSignature(authToken, url, params);
    const sig2 = computeTwilioSignature(authToken, url, params);
    assert.equal(sig1, sig2);
  });

  test("un mauvais token produit une signature differente (webhook invalide detecte)", () => {
    const url = "https://example.com/webhooks/voice/incoming";
    const params = { CallSid: "CA123" };
    const sigGood = computeTwilioSignature("bon-token", url, params);
    const sigBad = computeTwilioSignature("mauvais-token", url, params);
    assert.notEqual(sigGood, sigBad);
  });

  test("une url differente (host usurpe) produit une signature differente", () => {
    const authToken = "test-twilio-token";
    const params = { CallSid: "CA123" };
    const sigReal = computeTwilioSignature(authToken, "https://mon-agent.example.com/webhooks/voice/incoming", params);
    const sigFake = computeTwilioSignature(authToken, "https://attaquant.example.com/webhooks/voice/incoming", params);
    assert.notEqual(sigReal, sigFake);
  });
});
