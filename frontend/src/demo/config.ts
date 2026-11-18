/**
 * UI configuration. Products, locations, trucks, assumptions and calibration are NOT stored here:
 * they are loaded from the FreshSense backend at startup (initConfig) so the dashboard always shows
 * the same data-calibrated model the backend runs.
 */
import ui from "../data/demo.json";
import type { Product, ProductId, Location, Stage, Status, Truck, World } from "./types";
import type { IconName } from "../components/Icon";

export const API_BASE: string = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export const WS_URL: string = import.meta.env.VITE_WS_URL || API_BASE.replace(/^http/, "ws") + "/ws";

export const PRODUCTS: Record<ProductId, Product> = {};
export const LOCATIONS: Location[] = [];
export const TRUCKS: Partial<Truck>[] = [];
export const ASSUMPTIONS: Record<string, any> = {};
export const CALIBRATION: Record<string, any> = {};
export const DEMO = { ...ui, hero_crate_id: "", problem_truck_id: "" };
export const CONFIG = ui.simulation;

export function initConfig(meta: any, calibration: any, state: World) {
  Object.assign(PRODUCTS, meta.products);
  LOCATIONS.splice(0, LOCATIONS.length, ...meta.locations);
  TRUCKS.splice(0, TRUCKS.length, ...meta.trucks);
  Object.assign(ASSUMPTIONS, meta.assumptions);
  Object.assign(CALIBRATION, calibration);
  CONFIG.truck_speed_kmh = ASSUMPTIONS.truck_speed_kmh ?? CONFIG.truck_speed_kmh;
  CONFIG.road_factor = ASSUMPTIONS.road_factor ?? CONFIG.road_factor;
  setDemoTargets(state);
}

/** The demo's focus crate/truck = the most urgent crate in the backend's FEFO order. */
export function setDemoTargets(state: World) {
  const top = state.dispatch?.fefo?.[0]?.crate_id;
  const crate = state.crates.find((c) => c.id === top) ?? state.crates.find((c) => c.truck_id);
  DEMO.hero_crate_id = crate?.id ?? state.crates[0]?.id ?? "";
  DEMO.problem_truck_id = crate?.truck_id ?? state.trucks[0]?.id ?? "";
}

export const STAGES: Record<Stage, string> = {
  farm_pickup: "Pickup & pre-cooling",
  loading_dock: "Loading dock",
  cold_room: "Cold room",
  in_transit: "In transit",
  at_warehouse: "At warehouse",
};
const ICONS: Record<string, IconName> = {
  chicken: "chicken",
  beef: "chicken",
  dairy: "milk",
  greens: "leaf",
  strawberries: "heart",
};
export const PRODUCT_ICONS: Record<ProductId, IconName> = new Proxy(ICONS, {
  get: (t, k: string) => t[k] ?? "box",
});
export const NETWORK = [
  { type: "warehouse", label: "Hyperpure", description: "Warehouses", icon: "warehouse" as IconName },
  { type: "dark_store", label: "Blinkit", description: "Dark stores", icon: "box" as IconName },
  { type: "restaurant", label: "Zomato", description: "Partner restaurants", icon: "store" as IconName },
  { type: "food_bank", label: "Feeding India", description: "Donation partners", icon: "heart" as IconName },
];
export const getLocation = (id: string | null) => LOCATIONS.find((l) => l.id === id);
export const statusInfo = (status: Status) => DEMO.statuses.find((s) => s.id === status)!;
export const timeLabel = (ts: string) =>
  new Date(ts).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
export const number = (value: number | null | undefined, digits = 1) =>
  value == null || !Number.isFinite(value)
    ? "—"
    : value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
