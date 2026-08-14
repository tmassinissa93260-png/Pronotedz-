import * as store from "../businesses/store";

export const HAIRDRESSER_ID = "test-hairdresser";
export const FASTFOOD_ID = "test-fastfood";
export const RESTAURANT_ID = "test-restaurant";

let seeded = false;

export function ensureFixtures(): void {
  if (seeded) return;
  seeded = true;

  store.createBusiness({
    id: HAIRDRESSER_ID,
    type: "hairdresser",
    name: "Test Salon",
    phone: "+213555000001",
    address: "Adresse test",
    timezone: "Africa/Algiers",
    openHour: 9,
    closeHour: 19,
    slotMinutes: 30,
  });
  store.createService({ id: "svc-coupe-h", businessId: HAIRDRESSER_ID, name: "Coupe homme", durationMinutes: 30, price: 800 });
  store.createService({ id: "svc-coloration", businessId: HAIRDRESSER_ID, name: "Coloration", durationMinutes: 90, price: 3500 });

  store.createBusiness({
    id: FASTFOOD_ID,
    type: "fastfood",
    name: "Test Fast Food",
    phone: "+213555000002",
    address: "Adresse test",
    timezone: "Africa/Algiers",
    openHour: 10,
    closeHour: 23,
    slotMinutes: 15,
  });
  store.createMenuItem({ id: "menu-tacos", businessId: FASTFOOD_ID, name: "Tacos poulet", category: "Tacos", price: 550, description: "..." });
  store.createMenuItem({ id: "menu-frites", businessId: FASTFOOD_ID, name: "Frites", category: "Accompagnements", price: 200, description: "..." });

  store.createBusiness({
    id: RESTAURANT_ID,
    type: "restaurant",
    name: "Test Restaurant",
    phone: "+213555000003",
    address: "Adresse test",
    timezone: "Africa/Algiers",
    openHour: 12,
    closeHour: 23,
    slotMinutes: 30,
  });
  store.createMenuItem({ id: "menu-couscous", businessId: RESTAURANT_ID, name: "Couscous", category: "Plats", price: 1800, description: "..." });
  store.createTable({ id: "test-table-1", businessId: RESTAURANT_ID, capacity: 2 });
  store.createTable({ id: "test-table-2", businessId: RESTAURANT_ID, capacity: 4 });
}

// Date/heure future fixe utilisee par les tests pour eviter toute dependance
// a la date d'execution (doit rester dans le futur pour ne pas etre rejetee
// comme "reservation dans le passe").
export const FUTURE_DATE = "2099-06-15";
export function futureDatetime(hhmm: string): string {
  return `${FUTURE_DATE}T${hhmm}:00`;
}
