import { test, describe } from "node:test";
import assert from "node:assert/strict";
import * as store from "../businesses/store";
import { markEventProcessedOnce } from "../businesses/store";
import { ensureFixtures, HAIRDRESSER_ID, FASTFOOD_ID } from "./fixtures";

ensureFixtures();

describe("conversation: isolation par (channel, user, business)", () => {
  test("conversation multi-tour: l'historique est bien conserve et accumule", () => {
    const conv = store.getOrCreateConversation("webchat", "user-multiturn", HAIRDRESSER_ID);
    conv.history.push({ role: "user", content: "bonjour" });
    conv.history.push({ role: "assistant", content: "bonjour, comment puis-je vous aider ?" });
    store.saveConversation(conv);

    const reloaded = store.getOrCreateConversation("webchat", "user-multiturn", HAIRDRESSER_ID);
    assert.equal(reloaded.history.length, 2);
    assert.equal(reloaded.id, conv.id);

    reloaded.history.push({ role: "user", content: "je veux un rendez-vous" });
    store.saveConversation(reloaded);

    const reloadedAgain = store.getOrCreateConversation("webchat", "user-multiturn", HAIRDRESSER_ID);
    assert.equal(reloadedAgain.history.length, 3);
  });

  test("changement de canal = conversation distincte pour le meme identifiant utilisateur", () => {
    const sameId = "+213555200000";
    const whatsappConv = store.getOrCreateConversation("whatsapp", sameId, HAIRDRESSER_ID);
    whatsappConv.history.push({ role: "user", content: "message whatsapp" });
    store.saveConversation(whatsappConv);

    const voiceConv = store.getOrCreateConversation("voice", sameId, HAIRDRESSER_ID);
    assert.notEqual(voiceConv.id, whatsappConv.id);
    assert.equal(voiceConv.history.length, 0, "le canal voix ne doit pas voir l'historique whatsapp");
  });

  test("meme utilisateur/canal mais commerces differents = conversations distinctes", () => {
    const userId = "session-cross-business";
    const convA = store.getOrCreateConversation("webchat", userId, HAIRDRESSER_ID);
    convA.history.push({ role: "user", content: "je veux une coupe" });
    store.saveConversation(convA);

    const convB = store.getOrCreateConversation("webchat", userId, FASTFOOD_ID);
    assert.notEqual(convB.id, convA.id);
    assert.equal(convB.history.length, 0, "le fast-food ne doit pas voir l'historique du salon");
  });
});

describe("webhook: deduplication anti-replay", () => {
  test("le meme evenement traite deux fois n'est marque nouveau qu'une seule fois", () => {
    const first = markEventProcessedOnce("whatsapp", "wamid.TEST123");
    const second = markEventProcessedOnce("whatsapp", "wamid.TEST123");
    assert.equal(first, true, "premiere occurrence: doit etre traitee");
    assert.equal(second, false, "rejeu: doit etre ignore");
  });

  test("le meme event_id sur un canal different n'est pas confondu", () => {
    const onWhatsapp = markEventProcessedOnce("whatsapp", "shared-id-1");
    const onMessenger = markEventProcessedOnce("messenger", "shared-id-1");
    assert.equal(onWhatsapp, true);
    assert.equal(onMessenger, true, "les canaux ont des espaces d'identifiants independants");
  });
});
