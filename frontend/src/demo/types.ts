export type ProductId = string; // products come from the backend calibration (chicken, dairy, greens, strawberries, beef)
export type Stage = "farm_pickup" | "loading_dock" | "cold_room" | "in_transit" | "at_warehouse";
export type Status = "fresh" | "watch" | "at_risk" | "critical" | "spoiled";
export type Point = [number, number];
export interface Product {
  id: string;
  label: string;
  emoji: string;
  t_ref_c: number;
  max_safe_c: number;
  weight_kg: number;
  simulate: boolean;
  gas_model: boolean;
  foodkeeper_entry: string;
  foodkeeper_fridge_days: number[];
  model_shelf_life_days_at_ref: number;
}
export interface Location {
  id: string;
  name: string;
  type: "warehouse" | "dark_store" | "restaurant" | "food_bank";
  area: string;
  lat: number;
  lng: number;
  min_hours_needed: number | null;
  has_cold_room: boolean;
  demand_kg_per_day: Record<ProductId, number>;
}
export interface Crate {
  id: string;
  product: ProductId;
  product_label: string;
  weight_kg: number;
  truck_id: string | null;
  stage: Stage;
  temp_c: number;
  humidity: number;
  voc_index: number | null;
  door_open: boolean;
  tvc: number;
  tvc_kinetic: number;
  tvc_gas: number | null;
  quality_stage: string;
  freshness_score: number;
  hours_left: number;
  hours_left_if_unchanged: number;
  status: Status;
  loaded_at: string;
  destination_id: string | null;
  destination_name: string | null;
  original_destination_id: string | null;
  redirected: boolean;
  redirect_reason: string | null;
  eta_min: number | null;
  is_live_tag: boolean;
  lat: number;
  lng: number;
  heat_active?: boolean;
  delivered: boolean;
  discarded: boolean;
  delivered_to: string | null;
  warehouse_id: string;
}
export interface Truck {
  id: string;
  name: string;
  driver: string;
  color: string;
  origin_id: string;
  air_temp_c?: number;
  status: "en_route" | "at_warehouse";
  lat: number;
  lng: number;
  compressor_ok: boolean;
  door_open: boolean;
  completed?: boolean;
  stops: { location_id: string; crate_ids: string[]; eta_min: number }[];
  route_points: Point[];
  crate_ids: string[];
  extra_loss_h: number;
  excursions: number;
}
export interface Alert {
  id: string;
  ts: string;
  type: string;
  severity: "warning" | "critical" | "info";
  crate_id: string | null;
  truck_id: string | null;
  message: string;
}
export interface Redirect {
  id: string;
  ts: string;
  crate_id: string;
  truck_id: string;
  product: ProductId;
  weight_kg: number;
  hours_left: number;
  decision: "REDIRECT" | "DONATE" | "DISCARD";
  from_location_id: string | null;
  to_location_id: string | null;
  from_point: Point;
  travel_min: number;
  reason: string;
  alternatives: { location_id: string; name: string; score: number }[];
  kg_saved: number;
}
export interface Delivery {
  id: string;
  ts: string;
  crate_id: string;
  location_id: string;
  accepted: boolean;
  hours_left: number;
}
export interface Impact {
  crates_redirected: number;
  crates_donated: number;
  kg_saved: number;
  rejections_avoided: number;
  deliveries_completed: number;
  deliveries_rejected: number;
  kg_wasted: number;
}
export interface Reading {
  ts: string;
  temp_c: number;
  humidity: number;
  voc_index: number | null;
  tvc: number;
  freshness_score: number;
  stage: Stage;
}
export interface World {
  type: "state";
  tick: number;
  sim_time: string;
  paused: boolean;
  minutes_per_tick: number;
  seed?: number;
  crates: Crate[];
  archive: Crate[];
  trucks: Truck[];
  alerts: Alert[];
  new_alerts: Alert[];
  redirects: Redirect[];
  new_redirects: Redirect[];
  deliveries: Delivery[];
  impact: Impact;
  dispatch: {
    fefo: { rank: number; crate_id: string; hours_left: number; destination_id: string | null; feasible: boolean }[];
    fifo: { rank: number; crate_id: string; hours_left: number; destination_id: string | null; feasible: boolean; would_be_rejected: boolean }[];
  };
}
export type DemoAction =
  | { type: "control"; paused?: boolean; minutes_per_tick?: number }
  | { type: "reset" }
  | { type: "heat"; id: string; minutes?: number }
  | { type: "shock"; id: string }
  | { type: "door" | "fail" | "fix"; id: string }
  | { type: "tag"; reading: { temp_c: number; humidity: number; door_open: boolean } };
