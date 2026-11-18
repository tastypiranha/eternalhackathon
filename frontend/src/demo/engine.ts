/**
 * Client-side helpers only. All simulation, freshness modelling and redirect decisions run in the backend;
 * this file just mirrors the backend's feasibility rule for table hints.
 */
import { CONFIG } from "./config";
import type { Crate, Location, Point } from "./types";

export function distance(a: Point, b: Point) {
  const r = 6371,
    rad = (n: number) => (n * Math.PI) / 180;
  const h =
    Math.sin(rad(b[0] - a[0]) / 2) ** 2 +
    Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(rad(b[1] - a[1]) / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}
export const travelHours = (crate: Pick<Crate, "lat" | "lng">, place: Location) =>
  (distance([crate.lat, crate.lng], [place.lat, place.lng]) * CONFIG.road_factor) / CONFIG.truck_speed_kmh;
export const feasible = (c: Crate, l: Location) =>
  l.min_hours_needed !== null &&
  (l.demand_kg_per_day[c.product] ?? 0) > 0 &&
  c.status !== "spoiled" &&
  c.hours_left - travelHours(c, l) >= l.min_hours_needed;
