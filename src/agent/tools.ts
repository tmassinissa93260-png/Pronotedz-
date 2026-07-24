import Anthropic from "@anthropic-ai/sdk";
import { Business } from "../businesses/types";
import * as store from "../businesses/store";

type ToolDef = Anthropic.Tool;

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
      datetime: { type: "string", description: "Date et heure ISO 8601, ex: 2026-07-25T10:30:00" },
      customer_name: { type: "string" },
      customer_phone: { type: "string" },
    },
    required: ["service_id", "datetime", "customer_name", "customer_phone"],
  },
};

const CANCEL_BOOKING: ToolDef = {
  name: "cancel_booking",
  description: "Annule un rendez-vous existant a partir de son identifiant.",
  input_schema: {
    type: "object",
    properties: { booking_id: { type: "string" } },
    required: ["booking_id"],
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
            quantity: { type: "integer", minimum: 1 },
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
      party_size: { type: "integer", minimum: 1 },
      datetime: { type: "string", description: "Date et heure ISO 8601." },
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
      party_size: { type: "integer", minimum: 1 },
      datetime: { type: "string" },
      customer_name: { type: "string" },
      customer_phone: { type: "string" },
    },
    required: ["party_size", "datetime", "customer_name", "customer_phone"],
  },
};

const CANCEL_TABLE_RESERVATION: ToolDef = {
  name: "cancel_table_reservation",
  description: "Annule une reservation de table existante.",
  input_schema: {
    type: "object",
    properties: { reservation_id: { type: "string" } },
    required: ["reservation_id"],
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

function generateSlots(business: Business, date: string, durationMinutes: number): string[] {
  const slots: string[] = [];
  const [y, m, d] = date.split("-").map(Number);
  for (let h = business.openHour; h < business.closeHour; h++) {
    for (let min = 0; min < 60; min += business.slotMinutes) {
      const dt = new Date(y, m - 1, d, h, min, 0);
      const iso = dt.toISOString().slice(0, 19);
      if (store.isSlotFree(business.id, iso, durationMinutes)) {
        slots.push(`${String(h).padStart(2, "0")}:${String(min).padStart(2, "0")}`);
      }
    }
  }
  return slots;
}

export function executeTool(business: Business, name: string, input: any): string {
  switch (name) {
    case "check_availability": {
      const services = store.listServices(business.id);
      const service = services.find((s) => s.id === input.service_id);
      if (!service) return JSON.stringify({ error: "service_id inconnu" });
      const slots = generateSlots(business, input.date, service.durationMinutes);
      return JSON.stringify({ date: input.date, service: service.name, available_slots: slots });
    }
    case "create_booking": {
      const services = store.listServices(business.id);
      const service = services.find((s) => s.id === input.service_id);
      if (!service) return JSON.stringify({ error: "service_id inconnu" });
      if (!store.isSlotFree(business.id, input.datetime, service.durationMinutes)) {
        return JSON.stringify({ error: "Creneau indisponible, propose une verification a nouveau." });
      }
      const booking = store.createBooking({
        businessId: business.id,
        serviceId: service.id,
        customerName: input.customer_name,
        customerPhone: input.customer_phone,
        datetime: input.datetime,
      });
      return JSON.stringify({ success: true, booking });
    }
    case "cancel_booking": {
      const ok = store.cancelBooking(input.booking_id);
      return JSON.stringify({ success: ok });
    }
    case "check_table_availability": {
      const table = store.findAvailableTable(business.id, input.party_size, input.datetime);
      return JSON.stringify({ available: !!table, table_id: table?.id ?? null });
    }
    case "create_table_reservation": {
      const table = store.findAvailableTable(business.id, input.party_size, input.datetime);
      if (!table) return JSON.stringify({ error: "Aucune table disponible pour ce creneau." });
      const reservation = store.createTableReservation({
        businessId: business.id,
        tableId: table.id,
        partySize: input.party_size,
        customerName: input.customer_name,
        customerPhone: input.customer_phone,
        datetime: input.datetime,
      });
      return JSON.stringify({ success: true, reservation });
    }
    case "cancel_table_reservation": {
      const ok = store.cancelTableReservation(input.reservation_id);
      return JSON.stringify({ success: ok });
    }
    case "create_order": {
      const menu = store.listMenuItems(business.id);
      const items = [];
      for (const it of input.items) {
        const menuItem = menu.find((m) => m.id === it.menu_item_id);
        if (!menuItem) return JSON.stringify({ error: `menu_item_id inconnu: ${it.menu_item_id}` });
        items.push({ menuItemId: menuItem.id, name: menuItem.name, quantity: it.quantity, unitPrice: menuItem.price });
      }
      if (input.order_type === "delivery" && !input.address) {
        return JSON.stringify({ error: "Adresse requise pour une livraison." });
      }
      const order = store.createOrder({
        businessId: business.id,
        customerName: input.customer_name,
        customerPhone: input.customer_phone,
        items,
        orderType: input.order_type,
        address: input.address ?? null,
      });
      return JSON.stringify({ success: true, order });
    }
    default:
      return JSON.stringify({ error: `Outil inconnu: ${name}` });
  }
}
