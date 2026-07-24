import { nanoid } from "nanoid";
import { db } from "../db/client";
import {
  Booking,
  Business,
  ConversationRecord,
  MenuItem,
  Order,
  OrderItem,
  OrderType,
  RestaurantTable,
  Service,
  TableReservation,
} from "./types";

function rowToBusiness(r: any): Business {
  return {
    id: r.id,
    type: r.type,
    name: r.name,
    phone: r.phone,
    address: r.address,
    timezone: r.timezone,
    openHour: r.open_hour,
    closeHour: r.close_hour,
    slotMinutes: r.slot_minutes,
  };
}

export function getBusiness(id: string): Business | null {
  const row = db.prepare("SELECT * FROM businesses WHERE id = ?").get(id);
  return row ? rowToBusiness(row) : null;
}

export function listBusinesses(): Business[] {
  const rows = db.prepare("SELECT * FROM businesses").all();
  return rows.map(rowToBusiness);
}

export function createBusiness(b: Business): void {
  db.prepare(
    `INSERT INTO businesses (id, type, name, phone, address, timezone, open_hour, close_hour, slot_minutes)
     VALUES (@id, @type, @name, @phone, @address, @timezone, @openHour, @closeHour, @slotMinutes)`
  ).run(b);
}

export function listServices(businessId: string): Service[] {
  const rows = db.prepare("SELECT * FROM services WHERE business_id = ?").all(businessId);
  return rows.map((r: any) => ({
    id: r.id,
    businessId: r.business_id,
    name: r.name,
    durationMinutes: r.duration_minutes,
    price: r.price,
  }));
}

export function createService(s: Service): void {
  db.prepare(
    `INSERT INTO services (id, business_id, name, duration_minutes, price)
     VALUES (@id, @businessId, @name, @durationMinutes, @price)`
  ).run(s);
}

export function listMenuItems(businessId: string): MenuItem[] {
  const rows = db.prepare("SELECT * FROM menu_items WHERE business_id = ?").all(businessId);
  return rows.map((r: any) => ({
    id: r.id,
    businessId: r.business_id,
    name: r.name,
    category: r.category,
    price: r.price,
    description: r.description,
  }));
}

export function createMenuItem(m: MenuItem): void {
  db.prepare(
    `INSERT INTO menu_items (id, business_id, name, category, price, description)
     VALUES (@id, @businessId, @name, @category, @price, @description)`
  ).run(m);
}

export function listTables(businessId: string): RestaurantTable[] {
  const rows = db.prepare("SELECT * FROM restaurant_tables WHERE business_id = ?").all(businessId);
  return rows.map((r: any) => ({ id: r.id, businessId: r.business_id, capacity: r.capacity }));
}

export function createTable(t: RestaurantTable): void {
  db.prepare(
    `INSERT INTO restaurant_tables (id, business_id, capacity) VALUES (@id, @businessId, @capacity)`
  ).run(t);
}

// --- Availability & bookings (hairdresser-style single-resource scheduling) ---

export function listBookingsForDay(businessId: string, isoDate: string): Booking[] {
  const rows = db
    .prepare(
      `SELECT * FROM bookings WHERE business_id = ? AND status = 'confirmed' AND date(datetime) = date(?)`
    )
    .all(businessId, isoDate);
  return rows.map(rowToBooking);
}

function rowToBooking(r: any): Booking {
  return {
    id: r.id,
    businessId: r.business_id,
    serviceId: r.service_id,
    customerName: r.customer_name,
    customerPhone: r.customer_phone,
    datetime: r.datetime,
    status: r.status,
  };
}

export function isSlotFree(businessId: string, datetimeIso: string, durationMinutes: number): boolean {
  const start = new Date(datetimeIso).getTime();
  const end = start + durationMinutes * 60000;
  const dayBookings = listBookingsForDay(businessId, datetimeIso);
  const services = new Map(listServices(businessId).map((s) => [s.id, s]));
  for (const b of dayBookings) {
    const bStart = new Date(b.datetime).getTime();
    const bDuration = services.get(b.serviceId)?.durationMinutes ?? 30;
    const bEnd = bStart + bDuration * 60000;
    if (start < bEnd && end > bStart) return false;
  }
  return true;
}

export function createBooking(input: {
  businessId: string;
  serviceId: string;
  customerName: string;
  customerPhone: string;
  datetime: string;
}): Booking {
  const booking: Booking = { id: nanoid(10), status: "confirmed", ...input };
  db.prepare(
    `INSERT INTO bookings (id, business_id, service_id, customer_name, customer_phone, datetime, status)
     VALUES (@id, @businessId, @serviceId, @customerName, @customerPhone, @datetime, @status)`
  ).run(booking);
  return booking;
}

export function cancelBooking(id: string): boolean {
  const res = db.prepare("UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status = 'confirmed'").run(id);
  return res.changes > 0;
}

export function getBooking(id: string): Booking | null {
  const row = db.prepare("SELECT * FROM bookings WHERE id = ?").get(id);
  return row ? rowToBooking(row as any) : null;
}

// --- Table reservations (restaurant) ---

export function findAvailableTable(
  businessId: string,
  partySize: number,
  datetimeIso: string,
  durationMinutes = 90
): RestaurantTable | null {
  const tables = listTables(businessId)
    .filter((t) => t.capacity >= partySize)
    .sort((a, b) => a.capacity - b.capacity);

  const start = new Date(datetimeIso).getTime();
  const end = start + durationMinutes * 60000;
  const dayReservations = db
    .prepare(
      `SELECT * FROM table_reservations WHERE business_id = ? AND status = 'confirmed' AND date(datetime) = date(?)`
    )
    .all(businessId, datetimeIso) as any[];

  for (const table of tables) {
    const conflict = dayReservations.some((r) => {
      if (r.table_id !== table.id) return false;
      const rStart = new Date(r.datetime).getTime();
      const rEnd = rStart + durationMinutes * 60000;
      return start < rEnd && end > rStart;
    });
    if (!conflict) return table;
  }
  return null;
}

export function createTableReservation(input: {
  businessId: string;
  tableId: string;
  partySize: number;
  customerName: string;
  customerPhone: string;
  datetime: string;
}): TableReservation {
  const reservation: TableReservation = { id: nanoid(10), status: "confirmed", ...input };
  db.prepare(
    `INSERT INTO table_reservations (id, business_id, table_id, party_size, customer_name, customer_phone, datetime, status)
     VALUES (@id, @businessId, @tableId, @partySize, @customerName, @customerPhone, @datetime, @status)`
  ).run(reservation);
  return reservation;
}

export function cancelTableReservation(id: string): boolean {
  const res = db
    .prepare("UPDATE table_reservations SET status = 'cancelled' WHERE id = ? AND status = 'confirmed'")
    .run(id);
  return res.changes > 0;
}

// --- Orders (fast-food / restaurant takeout-delivery) ---

export function createOrder(input: {
  businessId: string;
  customerName: string;
  customerPhone: string;
  items: OrderItem[];
  orderType: OrderType;
  address: string | null;
}): Order {
  const total = input.items.reduce((sum, i) => sum + i.unitPrice * i.quantity, 0);
  const order: Order = {
    id: nanoid(10),
    status: "received",
    createdAt: new Date().toISOString(),
    total,
    ...input,
  };
  db.prepare(
    `INSERT INTO orders (id, business_id, customer_name, customer_phone, items, total, order_type, address, status, created_at)
     VALUES (@id, @businessId, @customerName, @customerPhone, @items, @total, @orderType, @address, @status, @createdAt)`
  ).run({ ...order, items: JSON.stringify(order.items) });
  return order;
}

export function getOrder(id: string): Order | null {
  const row = db.prepare("SELECT * FROM orders WHERE id = ?").get(id) as any;
  if (!row) return null;
  return { ...row, items: JSON.parse(row.items), businessId: row.business_id, customerName: row.customer_name, customerPhone: row.customer_phone, orderType: row.order_type, createdAt: row.created_at };
}

// --- Conversations (per channel + external user + business) ---

export function getOrCreateConversation(
  channel: string,
  externalUserId: string,
  businessId: string
): ConversationRecord {
  const row = db
    .prepare("SELECT * FROM conversations WHERE channel = ? AND external_user_id = ? AND business_id = ?")
    .get(channel, externalUserId, businessId) as any;
  if (row) {
    return {
      id: row.id,
      channel: row.channel,
      externalUserId: row.external_user_id,
      businessId: row.business_id,
      history: JSON.parse(row.history),
      updatedAt: row.updated_at,
    };
  }
  const record: ConversationRecord = {
    id: nanoid(12),
    channel,
    externalUserId,
    businessId,
    history: [],
    updatedAt: new Date().toISOString(),
  };
  db.prepare(
    `INSERT INTO conversations (id, channel, external_user_id, business_id, history, updated_at)
     VALUES (@id, @channel, @externalUserId, @businessId, @history, @updatedAt)`
  ).run({ ...record, history: JSON.stringify(record.history) });
  return record;
}

export function saveConversation(record: ConversationRecord): void {
  record.updatedAt = new Date().toISOString();
  db.prepare("UPDATE conversations SET history = ?, updated_at = ? WHERE id = ?").run(
    JSON.stringify(record.history),
    record.updatedAt,
    record.id
  );
}
