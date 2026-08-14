import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { withConversationLock } from "../agent/conversationLock";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

describe("conversationLock: serialisation des appels concurrents", () => {
  test("deux appels concurrents sur la meme cle s'executent sequentiellement", async () => {
    const key = "webchat:user-1:business-1";
    const order: string[] = [];

    const runA = withConversationLock(key, async () => {
      order.push("A-start");
      await delay(30);
      order.push("A-end");
      return "A";
    });
    // Lance B pendant que A tourne encore.
    await delay(5);
    const runB = withConversationLock(key, async () => {
      order.push("B-start");
      await delay(5);
      order.push("B-end");
      return "B";
    });

    const [resultA, resultB] = await Promise.all([runA, runB]);
    assert.equal(resultA, "A");
    assert.equal(resultB, "B");
    // B ne doit demarrer qu'apres la fin complete de A (pas d'entrelacement).
    assert.deepEqual(order, ["A-start", "A-end", "B-start", "B-end"]);
  });

  test("des cles differentes ne se bloquent pas entre elles", async () => {
    const order: string[] = [];
    const runA = withConversationLock("webchat:user-1:biz", async () => {
      order.push("A-start");
      await delay(30);
      order.push("A-end");
    });
    const runB = withConversationLock("webchat:user-2:biz", async () => {
      order.push("B-start");
      await delay(5);
      order.push("B-end");
    });
    await Promise.all([runA, runB]);
    // B (plus rapide, cle differente) doit pouvoir se terminer avant A.
    assert.deepEqual(order.slice(0, 2), ["A-start", "B-start"]);
    assert.equal(order.includes("B-end"), true);
    assert.ok(order.indexOf("B-end") < order.indexOf("A-end"));
  });

  test("une erreur dans un appel ne bloque pas les appels suivants sur la meme cle", async () => {
    const key = "webchat:user-err:biz";
    await assert.rejects(
      withConversationLock(key, async () => {
        throw new Error("boom");
      })
    );
    const result = await withConversationLock(key, async () => "ok apres erreur");
    assert.equal(result, "ok apres erreur");
  });
});
