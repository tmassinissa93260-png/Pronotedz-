import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { executeTool } from "../agent/tools";
import * as store from "../businesses/store";
import { ensureFixtures, HAIRDRESSER_ID, FASTFOOD_ID, RESTAURANT_ID, futureDatetime } from "./fixtures";

ensureFixtures();
const hairdresser = store.getBusiness(HAIRDRESSER_ID)!;
const fastfood = store.getBusiness(FASTFOOD_ID)!;
const restaurant = store.getBusiness(RESTAURANT_ID)!;

describe("booking: reservation reussie", () => {
  test("cree un rendez-vous valide", () => {
    const result = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "svc-coupe-h",
        datetime: futureDatetime("10:00"),
        customer_name: "Yanis",
        customer_phone: "+213555111222",
      })
    );
    assert.equal(result.success, true);
    assert.ok(result.booking.id);
    assert.equal(result.booking.status, "confirmed");
  });
});

describe("booking: creneau indisponible", () => {
  test("refuse un rendez-vous en dehors des horaires d'ouverture", () => {
    const result = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "svc-coupe-h",
        datetime: futureDatetime("23:30"), // salon ferme a 19h
        customer_name: "Karim",
        customer_phone: "+213555111333",
      })
    );
    assert.ok(result.error);
  });

  test("refuse une reservation dans le passe", () => {
    const result = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "svc-coupe-h",
        datetime: "2020-01-01T10:00:00",
        customer_name: "Karim",
        customer_phone: "+213555111333",
      })
    );
    assert.ok(result.error);
  });
});

describe("booking: double reservation", () => {
  test("le meme creneau ne peut pas etre reserve deux fois", () => {
    const slot = futureDatetime("11:00");
    const first = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "svc-coupe-h",
        datetime: slot,
        customer_name: "Client A",
        customer_phone: "+213555111444",
      })
    );
    assert.equal(first.success, true);

    const second = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "svc-coupe-h",
        datetime: slot,
        customer_name: "Client B",
        customer_phone: "+213555111555",
      })
    );
    assert.ok(second.error, "le deuxieme appel doit echouer");
  });

  test("un double appel identique et immediat (meme client) est aussi rejete au deuxieme essai", () => {
    const slot = futureDatetime("12:00");
    const args = {
      service_id: "svc-coupe-h",
      datetime: slot,
      customer_name: "Client C",
      customer_phone: "+213555111666",
    };
    const first = JSON.parse(executeTool(hairdresser, "create_booking", args));
    const second = JSON.parse(executeTool(hairdresser, "create_booking", args));
    assert.equal(first.success, true);
    assert.ok(second.error);
  });
});

describe("booking: annulation", () => {
  test("annulation reussie avec le bon telephone", () => {
    const created = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "svc-coupe-h",
        datetime: futureDatetime("13:00"),
        customer_name: "Sara",
        customer_phone: "+213555111777",
      })
    );
    const cancelled = JSON.parse(
      executeTool(hairdresser, "cancel_booking", {
        booking_id: created.booking.id,
        customer_phone: "+213555111777",
      })
    );
    assert.equal(cancelled.success, true);
  });

  test("annulation refusee si le telephone ne correspond pas (IDOR)", () => {
    const created = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "svc-coupe-h",
        datetime: futureDatetime("14:00"),
        customer_name: "Nadia",
        customer_phone: "+213555111888",
      })
    );
    const cancelled = JSON.parse(
      executeTool(hairdresser, "cancel_booking", {
        booking_id: created.booking.id,
        customer_phone: "+213555999999", // mauvais numero
      })
    );
    assert.ok(cancelled.error);

    // le rendez-vous doit rester confirme
    const booking = store.getBooking(created.booking.id);
    assert.equal(booking?.status, "confirmed");
  });

  test("annulation refusee depuis un autre commerce (isolation cross-tenant)", () => {
    const created = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "svc-coupe-h",
        datetime: futureDatetime("15:00"),
        customer_name: "Malik",
        customer_phone: "+213555112000",
      })
    );
    // meme telephone mais tentative d'annulation via un AUTRE business_id
    const ok = store.cancelBooking(created.booking.id, FASTFOOD_ID, "+213555112000");
    assert.equal(ok, false);
  });
});

describe("tool call invalide", () => {
  test("outil inconnu renvoie une erreur structuree, pas d'exception", () => {
    assert.doesNotThrow(() => {
      const result = JSON.parse(executeTool(hairdresser, "delete_everything", {}));
      assert.ok(result.error);
    });
  });

  test("champs requis manquants renvoient une erreur", () => {
    const result = JSON.parse(executeTool(hairdresser, "create_booking", { service_id: "svc-coupe-h" }));
    assert.ok(result.error);
  });

  test("service_id invalide (autre commerce) est rejete", () => {
    const result = JSON.parse(
      executeTool(hairdresser, "create_booking", {
        service_id: "menu-tacos", // appartient au fastfood, pas au salon
        datetime: futureDatetime("16:00"),
        customer_name: "Test",
        customer_phone: "+213555112111",
      })
    );
    assert.ok(result.error);
  });

  test("input non-objet (null) ne fait pas planter l'outil", () => {
    assert.doesNotThrow(() => {
      const result = JSON.parse(executeTool(hairdresser, "create_booking", null));
      assert.ok(result.error);
    });
  });
});

describe("orders: commande valide", () => {
  test("cree une commande avec le bon total calcule cote serveur", () => {
    const result = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [
          { menu_item_id: "menu-tacos", quantity: 2 },
          { menu_item_id: "menu-frites", quantity: 1 },
        ],
        customer_name: "Amine",
        customer_phone: "+213555113000",
        order_type: "pickup",
      })
    );
    assert.equal(result.success, true);
    // 2*550 + 1*200 = 1300
    assert.equal(result.order.total, 1300);
  });

  test("delivery sans adresse est refusee", () => {
    const result = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [{ menu_item_id: "menu-tacos", quantity: 1 }],
        customer_name: "Amine",
        customer_phone: "+213555113001",
        order_type: "delivery",
      })
    );
    assert.ok(result.error);
  });
});

describe("orders: produit inexistant", () => {
  test("menu_item_id inconnu rejette toute la commande", () => {
    const result = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [{ menu_item_id: "produit-invente-par-le-modele", quantity: 1 }],
        customer_name: "Test",
        customer_phone: "+213555113002",
        order_type: "pickup",
      })
    );
    assert.ok(result.error);
  });
});

describe("orders: prix falsifie", () => {
  test("un prix ou total injecte dans l'input est ignore, seul le prix serveur compte", () => {
    const result = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [
          // le modele (ou un attaquant appelant l'outil directement) tente
          // d'injecter un prix / total arbitraire : ces champs ne sont pas
          // lus par l'outil, seul le menu stocke en base fait foi.
          { menu_item_id: "menu-tacos", quantity: 1, unitPrice: 1, price: 1, total: 1 },
        ],
        customer_name: "Attaquant",
        customer_phone: "+213555113003",
        order_type: "pickup",
        total: 1,
      })
    );
    assert.equal(result.success, true);
    assert.equal(result.order.total, 550, "le total doit venir du prix serveur (550), pas de l'input (1)");
  });

  test("quantite negative ou nulle est rejetee", () => {
    const negative = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [{ menu_item_id: "menu-tacos", quantity: -5 }],
        customer_name: "Test",
        customer_phone: "+213555113004",
        order_type: "pickup",
      })
    );
    assert.ok(negative.error);

    const zero = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [{ menu_item_id: "menu-tacos", quantity: 0 }],
        customer_name: "Test",
        customer_phone: "+213555113005",
        order_type: "pickup",
      })
    );
    assert.ok(zero.error);
  });

  test("quantite demesuree est rejetee", () => {
    const result = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [{ menu_item_id: "menu-tacos", quantity: 999999 }],
        customer_name: "Test",
        customer_phone: "+213555113006",
        order_type: "pickup",
      })
    );
    assert.ok(result.error);
  });

  test("quantite non entiere (string) est rejetee", () => {
    const result = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [{ menu_item_id: "menu-tacos", quantity: "2" as any }],
        customer_name: "Test",
        customer_phone: "+213555113007",
        order_type: "pickup",
      })
    );
    assert.ok(result.error);
  });
});

describe("orders: idempotence / double appel", () => {
  test("deux commandes identiques rapprochees renvoient la meme commande (dedup)", () => {
    const args = {
      items: [{ menu_item_id: "menu-tacos", quantity: 3 }],
      customer_name: "Client Dup",
      customer_phone: "+213555113008",
      order_type: "pickup" as const,
    };
    const first = JSON.parse(executeTool(fastfood, "create_order", args));
    const second = JSON.parse(executeTool(fastfood, "create_order", args));
    assert.equal(first.success, true);
    assert.equal(second.success, true);
    assert.equal(first.order.id, second.order.id, "la deuxieme commande doit reutiliser la premiere");
    assert.equal(second.already_existed, true);
  });

  test("des commandes differentes pour le meme client ne sont pas fusionnees", () => {
    const phone = "+213555113009";
    const first = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [{ menu_item_id: "menu-tacos", quantity: 1 }],
        customer_name: "Client",
        customer_phone: phone,
        order_type: "pickup",
      })
    );
    const second = JSON.parse(
      executeTool(fastfood, "create_order", {
        items: [{ menu_item_id: "menu-frites", quantity: 1 }],
        customer_name: "Client",
        customer_phone: phone,
        order_type: "pickup",
      })
    );
    assert.notEqual(first.order.id, second.order.id);
  });
});

describe("restaurant: reservation de table concurrente", () => {
  test("deux demandes pour la meme table/heure : une seule aboutit", () => {
    const slot = futureDatetime("19:30");
    const first = JSON.parse(
      executeTool(restaurant, "create_table_reservation", {
        party_size: 2,
        datetime: slot,
        customer_name: "Groupe A",
        customer_phone: "+213555114000",
      })
    );
    const second = JSON.parse(
      executeTool(restaurant, "create_table_reservation", {
        party_size: 2,
        datetime: slot,
        customer_name: "Groupe B",
        customer_phone: "+213555114001",
      })
    );
    assert.equal(first.success, true);
    // il n'y a que deux tables de capacite >=2 (2 et 4 places) donc une 2e
    // demande de 2 personnes au meme creneau peut encore trouver la table de
    // 4 places libre : on verifie plutot qu'une 3e demande simultanee echoue.
    const third = JSON.parse(
      executeTool(restaurant, "create_table_reservation", {
        party_size: 2,
        datetime: slot,
        customer_name: "Groupe C",
        customer_phone: "+213555114002",
      })
    );
    assert.equal(second.success, true);
    assert.ok(third.error, "plus aucune table disponible pour ce creneau");
  });

  test("party_size superieur a toutes les capacites est refuse proprement", () => {
    const result = JSON.parse(
      executeTool(restaurant, "create_table_reservation", {
        party_size: 25,
        datetime: futureDatetime("20:30"),
        customer_name: "Grand groupe",
        customer_phone: "+213555114003",
      })
    );
    assert.ok(result.error);
  });
});
