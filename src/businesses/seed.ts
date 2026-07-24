import { db } from "../db/client";
import {
  createBusiness,
  createMenuItem,
  createService,
  createTable,
  listBusinesses,
} from "./store";

export const DEMO_HAIRDRESSER_ID = "salon-belle-coupe";
export const DEMO_FASTFOOD_ID = "fast-o-poulet";
export const DEMO_RESTAURANT_ID = "chez-amina";

export function seed(): void {
  if (listBusinesses().length > 0) {
    console.log("Seed ignore: des commerces existent deja.");
    return;
  }

  createBusiness({
    id: DEMO_HAIRDRESSER_ID,
    type: "hairdresser",
    name: "Salon Belle Coupe",
    phone: "+213555000001",
    address: "12 Rue Didouche Mourad, Alger",
    timezone: "Africa/Algiers",
    openHour: 9,
    closeHour: 19,
    slotMinutes: 30,
  });
  createService({ id: "svc-coupe-h", businessId: DEMO_HAIRDRESSER_ID, name: "Coupe homme", durationMinutes: 30, price: 800 });
  createService({ id: "svc-coupe-f", businessId: DEMO_HAIRDRESSER_ID, name: "Coupe femme", durationMinutes: 45, price: 1500 });
  createService({ id: "svc-coloration", businessId: DEMO_HAIRDRESSER_ID, name: "Coloration", durationMinutes: 90, price: 3500 });
  createService({ id: "svc-barbe", businessId: DEMO_HAIRDRESSER_ID, name: "Taille de barbe", durationMinutes: 20, price: 500 });

  createBusiness({
    id: DEMO_FASTFOOD_ID,
    type: "fastfood",
    name: "Fast O Poulet",
    phone: "+213555000002",
    address: "45 Boulevard Zighout Youcef, Alger",
    timezone: "Africa/Algiers",
    openHour: 10,
    closeHour: 23,
    slotMinutes: 15,
  });
  createMenuItem({ id: "menu-tacos-poulet", businessId: DEMO_FASTFOOD_ID, name: "Tacos poulet", category: "Tacos", price: 550, description: "Tacos poulet, frites, sauce fromagere" });
  createMenuItem({ id: "menu-tacos-viande", businessId: DEMO_FASTFOOD_ID, name: "Tacos viande hachee", category: "Tacos", price: 600, description: "Tacos viande hachee, frites, sauce algerienne" });
  createMenuItem({ id: "menu-burger-classic", businessId: DEMO_FASTFOOD_ID, name: "Burger classique", category: "Burgers", price: 500, description: "Steak, cheddar, salade, tomate" });
  createMenuItem({ id: "menu-frites", businessId: DEMO_FASTFOOD_ID, name: "Frites", category: "Accompagnements", price: 200, description: "Portion de frites maison" });
  createMenuItem({ id: "menu-boisson", businessId: DEMO_FASTFOOD_ID, name: "Boisson 33cl", category: "Boissons", price: 100, description: "Coca, Fanta, Sprite" });

  createBusiness({
    id: DEMO_RESTAURANT_ID,
    type: "restaurant",
    name: "Chez Amina",
    phone: "+213555000003",
    address: "3 Rue Larbi Ben M'hidi, Alger",
    timezone: "Africa/Algiers",
    openHour: 12,
    closeHour: 23,
    slotMinutes: 30,
  });
  createMenuItem({ id: "menu-couscous", businessId: DEMO_RESTAURANT_ID, name: "Couscous royal", category: "Plats", price: 1800, description: "Couscous, agneau, poulet, merguez, legumes" });
  createMenuItem({ id: "menu-chorba", businessId: DEMO_RESTAURANT_ID, name: "Chorba", category: "Entrees", price: 400, description: "Soupe traditionnelle" });
  createMenuItem({ id: "menu-tajine", businessId: DEMO_RESTAURANT_ID, name: "Tajine pruneaux", category: "Plats", price: 1600, description: "Agneau, pruneaux, amandes" });
  createTable({ id: "table-1", businessId: DEMO_RESTAURANT_ID, capacity: 2 });
  createTable({ id: "table-2", businessId: DEMO_RESTAURANT_ID, capacity: 2 });
  createTable({ id: "table-3", businessId: DEMO_RESTAURANT_ID, capacity: 4 });
  createTable({ id: "table-4", businessId: DEMO_RESTAURANT_ID, capacity: 4 });
  createTable({ id: "table-5", businessId: DEMO_RESTAURANT_ID, capacity: 8 });

  console.log("Seed termine: 3 commerces demo crees.");
}

if (require.main === module) {
  seed();
  db.close();
}
