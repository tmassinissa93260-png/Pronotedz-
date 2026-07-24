export type BusinessType = "hairdresser" | "fastfood" | "restaurant";

export interface Business {
  id: string;
  type: BusinessType;
  name: string;
  phone: string;
  address: string;
  timezone: string;
  openHour: number;
  closeHour: number;
  slotMinutes: number;
}

export interface Service {
  id: string;
  businessId: string;
  name: string;
  durationMinutes: number;
  price: number;
}

export interface MenuItem {
  id: string;
  businessId: string;
  name: string;
  category: string;
  price: number;
  description: string;
}

export interface RestaurantTable {
  id: string;
  businessId: string;
  capacity: number;
}

export type BookingStatus = "confirmed" | "cancelled";

export interface Booking {
  id: string;
  businessId: string;
  serviceId: string;
  customerName: string;
  customerPhone: string;
  datetime: string; // ISO
  status: BookingStatus;
}

export interface TableReservation {
  id: string;
  businessId: string;
  tableId: string;
  partySize: number;
  customerName: string;
  customerPhone: string;
  datetime: string; // ISO
  status: BookingStatus;
}

export type OrderStatus = "received" | "preparing" | "ready" | "completed" | "cancelled";
export type OrderType = "pickup" | "delivery";

export interface OrderItem {
  menuItemId: string;
  name: string;
  quantity: number;
  unitPrice: number;
}

export interface Order {
  id: string;
  businessId: string;
  customerName: string;
  customerPhone: string;
  items: OrderItem[];
  total: number;
  orderType: OrderType;
  address: string | null;
  status: OrderStatus;
  createdAt: string; // ISO
}

export interface ConversationRecord {
  id: string;
  channel: string;
  externalUserId: string;
  businessId: string;
  history: { role: "user" | "assistant"; content: string }[];
  updatedAt: string;
}
