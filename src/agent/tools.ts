import Anthropic from "@anthropic-ai/sdk";
import { Business } from "../businesses/types";
import * as store from "../businesses/store";
import { formatNaive, isInThePast, isWithinBusinessHours, parseNaiveDate, parseNaiveDateTime } from "./datetime";
import {
  requireEnum,
  requireId,
  requireItemsArray,
  requireNonEmptyString,
  requirePhone,
  requirePositiveInt,
} from "./validate";

type ToolDef = Anthropic.Tool;

const MAX_PARTY_SIZE = 30;
const MAX_QUANTITY = 50;
const RESTAURANT_RESERVATION_DURATION_MINUTES = 90;

const CHECK_AVAILABILITY: ToolDef = {
  name: "check_availability",
  description:
    "Verifie les creneaux disponibles pour un service donne, a une date donnee (format YYYY-MM-DD). Retourne la liste des heures libres.",
  input_schema: {
    type: "object",
    properties: {
      service_id: { type: "string", description: "Identifiant du service (voir la liste des services fournie)." },
      date: { type: "string", description: "Date au format YYYY-MM-DD." },
    },
    required: ["service_id", "date"],
  },
};

const CREATE_BOOKING: ToolDef = {
  name: "create_booking",
  description: "Cree un rendez-vous confirme pour un client, apres avoir verifie la disponibilite.",
  input_schema: {
    type: "object",
    properties: {
      service_id: { type: "string" },
      datetime: { type: "string", description: "Date et heure locales du commerce, format 2026-07-25T10:30:00 (pas d'offset UTC)." },
      customer_name: { type: "string" },
      customer_phone: { type: "string" },
    },
    required: ["service_id", "datetime", "customer_name", "customer_phone"],
  },
};

const CANCEL_BOOKING: ToolDef = {
  name: "cancel_booking",
  description:
    "Annule un rendez-vous existant. Le numero de telephone doit correspondre exactement a celui utilise lors de la creation, pour verifier que le client est bien le proprietaire de la reservation.",
  input_schema: {
    type: "object",
    properties: {
      booking_id: { type: "string" },
      customer_phone: { type: "string", description: "Telephone utilise lors de la reservation, pour verification." },
    },
    required: ["booking_id", "customer_phone"],
  },
};

const CREATE_ORDER: ToolDef = {
  name: "create_order",
  description: "Enregistre une commande avec les articles du menu choisis par le client.",
  input_schema: {
    type: "object",
    properties: {
      items: {
        type: "array",
        items: {
          type: "object",
          properties: {
            menu_item_id: { type: "string" },
            quantity: { type: "integer", minimum: 1, maximum: MAX_QUANTITY },
          },
          required: ["menu_item_id", "quantity"],
        },
      },
      customer_name: { type: "string" },
      customer_phone: { type: "string" },
      order_type: { type: "string", enum: ["pickup", "delivery"] },
      address: { type: "string", description: "Requis si order_type = delivery." },
    },
    required: ["items", "customer_name", "customer_phone", "order_type"],
  },
};

const CHECK_TABLE_AVAILABILITY: ToolDef = {
  name: "check_table_availability",
  description: "Verifie si une table est disponible pour un nombre de personnes a une date/heure donnee.",
  input_schema: {
    type: "object",
    properties: {
      party_size: { type: "integer", minimum: 1, maximum: MAX_PARTY_SIZE },
      datetime: { type: "string", description: "Date et heure locales du commerce, format 2026-07-25T20:00:00." },
    },
    required: ["party_size", "datetime"],
  },
};

const CREATE_TABLE_RESERVATION: ToolDef = {
  name: "create_table_reservation",
  description: "Reserve une table pour un client, apres avoir verifie la disponibilite.",
  input_schema: {
    type: "object",
    properties: {
      party_size: { type: "integer", minimum: 1, maximum: MAX_PARTY_SIZE },
      datetime: { type: "string" },
      customer_name: { type: "string" },
      customer_phone: { type: "string" },
    },
    required: ["party_size", "datetime", "customer_name", "customer_phone"],
  },
};

const CANCEL_TABLE_RESERVATION: ToolDef = {
  name: "cancel_table_reservation",
  description:
    "Annule une reservation de table existante. Le numero de telephone doit correspondre a celui utilise lors de la reservation.",
  input_schema: {
    type: "object",
    properties: {
      reservation_id: { type: "string" },
      customer_phone: { type: "string" },
    },
    required: ["reservation_id", "customer_phone"],
  },
};

export function toolsForBusiness(business: Business): ToolDef[] {
  if (business.type === "hairdresser") {
    return [CHECK_AVAILABILITY, CREATE_BOOKING, CANCEL_BOOKING];
  }
  if (business.type === "fastfood") {
    return [CREATE_ORDER];
  }
  // restaurant: reservation de table + commande a emporter/livraison
  return [CHECK_TABLE_AVAILABILITY, CREATE_TABLE_RESERVATION, CANCEL_TABLE_RESERVATION, CREATE_ORDER];
}

function errorJson(error: string): string {
  return JSON.stringify({ error });
}

function generateSlots(business: Business, date: string, durationMinutes: number): string[] {
  const parsedDate = parseNaiveDate(date);
  if (!parsedDate) return [];
  const slots: string[] = [];
  for (let h = business.openHour; h < business.closeHour; h++) {
    for (let min = 0; min < 60; min += business.slotMinutes) {
      const iso = formatNaive(parsedDate.y, parsedDate.mo, parsedDate.d, h, min);
      const parsed = parseNaiveDateTime(iso)!;
      if (isInThePast(parsed, business.timezone)) continue;
      if (!isWithinBusinessHours(parsed, business.openHour, business.closeHour, durationMinutes)) continue;
      if (store.isSlotFree(business.id, iso, durationMinutes)) {
        slots.push(`${String(h).padStart(2, "0")}:${String(min).padStart(2, "0")}`);
      }
    }
  }
  return slots;
}

function validateBookingDatetime(
  business: Business,
  rawDatetime: unknown,
  durationMinutes: number
): { ok: true; iso: string } | { ok: false; error: string } {
  if (typeof rawDatetime !== "string") return { ok: false, error: "datetime doit etre une chaine ISO locale." };
  const parsed = parseNaiveDateTime(rawDatetime);
  if (!parsed) {
    return { ok: false, error: "datetime invalide, format attendu: YYYY-MM-DDTHH:MM:SS." };
  }
  if (isInThePast(parsed, business.timezone)) {
    return { ok: false, error: "Impossible de reserver dans le passe." };
  }
  if (!isWithinBusinessHours(parsed, business.openHour, business.closeHour, durationMinutes)) {
    return {
      ok: false,
      error: `Hors horaires d'ouverture (${business.openHour}h-${business.closeHour}h) pour la duree demandee.`,
    };
  }
  return { ok: true, iso: rawDatetime };
}

export function executeTool(business: Business, name: string, input: any): string {
  try {
    return executeToolUnsafe(business, name, input);
  } catch (err: any) {
    console.error(`Erreur inattendue dans l'outil ${name}:`, err);
    return errorJson("Une erreur interne est survenue, merci de reessayer.");
  }
}

function executeToolUnsafe(business: Business, name: string, input: any): string {
  input = input && typeof input === "object" ? input : {};

  switch (name) {
    case "check_availability": {
      const serviceIdV = requireId(input.service_id, "service_id");
      if (!serviceIdV.ok) return errorJson(serviceIdV.error);
      const dateV = requireNonEmptyString(input.date, "date", 10);
      if (!dateV.ok) return errorJson(dateV.error);
      if (!parseNaiveDate(dateV.value)) return errorJson("date invalide, format attendu: YYYY-MM-DD.");

      const service = store.listServices(business.id).find((s) => s.id === serviceIdV.value);
      if (!service) return errorJson("service_id inconnu pour ce commerce.");

      const slots = generateSlots(business, dateV.value, service.durationMinutes);
      return JSON.stringify({ date: dateV.value, service: service.name, available_slots: slots });
    }

    case "create_booking": {
      const serviceIdV = requireId(input.service_id, "service_id");
      if (!serviceIdV.ok) return errorJson(serviceIdV.error);
      const nameV = requireNonEmptyString(input.customer_name, "customer_name", 100);
      if (!nameV.ok) return errorJson(nameV.error);
      const phoneV = requirePhone(input.customer_phone);
      if (!phoneV.ok) return errorJson(phoneV.error);

      const service = store.listServices(business.id).find((s) => s.id === serviceIdV.value);
      if (!service) return errorJson("service_id inconnu pour ce commerce.");

      const dtV = validateBookingDatetime(business, input.datetime, service.durationMinutes);
      if (!dtV.ok) return errorJson(dtV.error);

      const result = store.createBookingIfAvailable({
        businessId: business.id,
        serviceId: service.id,
        customerName: nameV.value,
        customerPhone: phoneV.value,
        datetime: dtV.iso,
        durationMinutes: service.durationMinutes,
      });
      if (!result.ok) {
        return errorJson("Creneau indisponible, propose une autre heure apres nouvelle verification.");
      }
      return JSON.stringify({ success: true, booking: result.booking });
    }

    case "cancel_booking": {
      const idV = requireId(input.booking_id, "booking_id");
      if (!idV.ok) return errorJson(idV.error);
      const phoneV = requirePhone(input.customer_phone);
      if (!phoneV.ok) return errorJson(phoneV.error);

      const ok = store.cancelBooking(idV.value, business.id, phoneV.value);
      if (!ok) {
        return errorJson(
          "Annulation impossible : reservation introuvable, deja annulee, ou le numero de telephone ne correspond pas."
        );
      }
      return JSON.stringify({ success: true });
    }

    case "check_table_availability": {
      const partySizeV = requirePositiveInt(input.party_size, "party_size", MAX_PARTY_SIZE);
      if (!partySizeV.ok) return errorJson(partySizeV.error);
      const parsed = parseNaiveDateTime(input.datetime);
      if (!parsed) return errorJson("datetime invalide, format attendu: YYYY-MM-DDTHH:MM:SS.");
      if (isInThePast(parsed, business.timezone)) return errorJson("Impossible de reserver dans le passe.");
      if (!isWithinBusinessHours(parsed, business.openHour, business.closeHour, RESTAURANT_RESERVATION_DURATION_MINUTES)) {
        return errorJson(`Hors horaires d'ouverture (${business.openHour}h-${business.closeHour}h).`);
      }

      const table = store.findAvailableTable(business.id, partySizeV.value, input.datetime, RESTAURANT_RESERVATION_DURATION_MINUTES);
      return JSON.stringify({ available: !!table });
    }

    case "create_table_reservation": {
      const partySizeV = requirePositiveInt(input.party_size, "party_size", MAX_PARTY_SIZE);
      if (!partySizeV.ok) return errorJson(partySizeV.error);
      const nameV = requireNonEmptyString(input.customer_name, "customer_name", 100);
      if (!nameV.ok) return errorJson(nameV.error);
      const phoneV = requirePhone(input.customer_phone);
      if (!phoneV.ok) return errorJson(phoneV.error);
      const parsed = parseNaiveDateTime(input.datetime);
      if (!parsed) return errorJson("datetime invalide, format attendu: YYYY-MM-DDTHH:MM:SS.");
      if (isInThePast(parsed, business.timezone)) return errorJson("Impossible de reserver dans le passe.");
      if (!isWithinBusinessHours(parsed, business.openHour, business.closeHour, RESTAURANT_RESERVATION_DURATION_MINUTES)) {
        return errorJson(`Hors horaires d'ouverture (${business.openHour}h-${business.closeHour}h).`);
      }

      const result = store.createTableReservationIfAvailable({
        businessId: business.id,
        partySize: partySizeV.value,
        customerName: nameV.value,
        customerPhone: phoneV.value,
        datetime: input.datetime,
        durationMinutes: RESTAURANT_RESERVATION_DURATION_MINUTES,
      });
      if (!result.ok) return errorJson("Aucune table disponible pour ce creneau.");
      return JSON.stringify({ success: true, reservation: result.reservation });
    }

    case "cancel_table_reservation": {
      const idV = requireId(input.reservation_id, "reservation_id");
      if (!idV.ok) return errorJson(idV.error);
      const phoneV = requirePhone(input.customer_phone);
      if (!phoneV.ok) return errorJson(phoneV.error);

      const ok = store.cancelTableReservation(idV.value, business.id, phoneV.value);
      if (!ok) {
        return errorJson(
          "Annulation impossible : reservation introuvable, deja annulee, ou le numero de telephone ne correspond pas."
        );
      }
      return JSON.stringify({ success: true });
    }

    case "create_order": {
      const nameV = requireNonEmptyString(input.customer_name, "customer_name", 100);
      if (!nameV.ok) return errorJson(nameV.error);
      const phoneV = requirePhone(input.customer_phone);
      if (!phoneV.ok) return errorJson(phoneV.error);
      const orderTypeV = requireEnum(input.order_type, ["pickup", "delivery"] as const, "order_type");
      if (!orderTypeV.ok) return errorJson(orderTypeV.error);
      const itemsV = requireItemsArray(input.items);
      if (!itemsV.ok) return errorJson(itemsV.error);

      let address: string | null = null;
      if (orderTypeV.value === "delivery") {
        const addressV = requireNonEmptyString(input.address, "address", 300);
        if (!addressV.ok) return errorJson("Adresse requise et valide pour une livraison.");
        address = addressV.value;
      }

      const menu = store.listMenuItems(business.id);
      const items = [];
      for (const raw of itemsV.value) {
        const menuIdV = requireId(raw.menu_item_id, "menu_item_id");
        if (!menuIdV.ok) return errorJson(menuIdV.error);
        const qtyV = requirePositiveInt(raw.quantity, "quantity", MAX_QUANTITY);
        if (!qtyV.ok) return errorJson(qtyV.error);
        const menuItem = menu.find((m) => m.id === menuIdV.value);
        if (!menuItem) return errorJson(`Produit inconnu pour ce commerce: ${menuIdV.value}`);
        // Le prix vient TOUJOURS du menu stocke en base, jamais de l'input du modele.
        items.push({ menuItemId: menuItem.id, name: menuItem.name, quantity: qtyV.value, unitPrice: menuItem.price });
      }

      const { order, deduped } = store.createOrder({
        businessId: business.id,
        customerName: nameV.value,
        customerPhone: phoneV.value,
        items,
        orderType: orderTypeV.value,
        address,
      });
      return JSON.stringify({ success: true, order, already_existed: deduped });
    }

    default:
      return errorJson(`Outil inconnu: ${name}`);
  }
}
