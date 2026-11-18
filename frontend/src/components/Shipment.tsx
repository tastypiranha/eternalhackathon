import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { API_BASE, PRODUCT_ICONS, number, statusInfo } from "../demo/config";
import { Icon } from "./Icon";
import type { IconName } from "./Icon";

type Incident = { type: string; at_h: number; minutes: number; on: boolean };
const NETWORK_LABEL: Record<string, string> = {
  restaurant: "Zomato restaurant",
  dark_store: "Blinkit dark store",
  food_bank: "Feeding India",
};
const NETWORK_ICON: Record<string, IconName> = { restaurant: "store", dark_store: "box", food_bank: "heart" };
const STAGE_LABEL: Record<string, string> = {
  origin_loading: "Loading at origin",
  highway: "On the highway",
  arrival_dock: "Arrival dock",
};
const DECISION_TEXT: Record<string, string> = {
  DELIVER: "Delivered as planned",
  ASSIGN: "Routed to the best outlet",
  REDIRECT: "Redirected",
  DONATE: "Donated",
  DISCARD: "Discarded",
};

const PRESETS = [
  {
    id: "clean",
    label: "Clean run",
    detail: "Strawberries, Mahabaleshwar → Bengaluru by reefer. FreshSense picks the best outlet.",
    product: "strawberries", origin: "ORG-MBW", city: "BLR", vehicle: "reefer", packed: 12, printed: 5, planned: "",
    incidents: [] as { type: string; at_h?: number; minutes?: number }[],
  },
  {
    id: "redirect",
    label: "Compressor fails",
    detail: "Chicken planned for a Rajajinagar restaurant; 5 h compressor failure → redirected.",
    product: "chicken", origin: "ORG-NMK", city: "BLR", vehicle: "reefer", packed: 44, printed: 4, planned: "R-06",
    incidents: [{ type: "compressor", at_h: 2, minutes: 300 }],
  },
  {
    id: "donate",
    label: "Too late to sell",
    detail: "Older chicken, compressor failure and 90 min on the dock → donated to Feeding India.",
    product: "chicken", origin: "ORG-NMK", city: "BLR", vehicle: "reefer", packed: 54, printed: 4, planned: "R-06",
    incidents: [{ type: "compressor", at_h: 2, minutes: 300 }, { type: "dock", minutes: 90 }],
  },
];

const post = (path: string, body: unknown) =>
  fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => {
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
    return d;
  });

const hm = (minute: number) => `${Math.floor(minute / 60)}h ${String(Math.round(minute % 60)).padStart(2, "0")}m`;

export function Shipment() {
  const [opts, setOpts] = useState<any>(null);
  const [product, setProduct] = useState("strawberries");
  const [origin, setOrigin] = useState("ORG-MBW");
  const [city, setCity] = useState("BLR");
  const [vehicle, setVehicle] = useState("reefer");
  const [packed, setPacked] = useState(12);
  const [printed, setPrinted] = useState(5);
  const [planned, setPlanned] = useState("");
  const [incidents, setIncidents] = useState<Incident[]>([
    { type: "door", at_h: 3, minutes: 10, on: false },
    { type: "compressor", at_h: 6, minutes: 240, on: false },
    { type: "shock", at_h: 9, minutes: 1, on: false },
    { type: "dock", at_h: 0, minutes: 90, on: false },
  ]);
  const [result, setResult] = useState<any>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRejected, setShowRejected] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  useEffect(() => {
    fetch(API_BASE + "/api/shipments/options")
      .then((r) => {
        if (!r.ok) throw new Error(`Backend has no shipment API (HTTP ${r.status}). Restart the backend.`);
        return r.json();
      })
      .then(setOpts)
      .catch((e) => setError(e.message));
  }, []);

  const cityObj = opts?.cities.find((c: any) => c.id === city);
  const originsForProduct = (opts?.origins ?? []).filter((o: any) => o.products.includes(product));
  useEffect(() => {
    if (opts && !originsForProduct.some((o: any) => o.id === origin) && originsForProduct[0])
      setOrigin(originsForProduct[0].id);
  }, [product, opts]); // eslint-disable-line react-hooks/exhaustive-deps
  const plannedValid = cityObj?.outlets.some((l: any) => l.id === planned) ? planned : "";
  const applyPreset = (pr: (typeof PRESETS)[number]) => {
    setProduct(pr.product);
    setOrigin(pr.origin);
    setCity(pr.city);
    setVehicle(pr.vehicle);
    setPacked(pr.packed);
    setPrinted(pr.printed);
    setPlanned(pr.planned);
    setIncidents((all) =>
      all.map((x) => {
        const m = pr.incidents.find((i) => i.type === x.type);
        return m ? { ...x, ...m, on: true } : { ...x, on: false };
      }),
    );
    setResult(null);
  };

  // playback
  const last = result ? result.timeline.length - 1 : 0;
  useEffect(() => {
    clearInterval(timer.current);
    if (!playing || !result) return;
    timer.current = setInterval(() => {
      setIdx((i) => {
        if (i >= last) {
          setPlaying(false);
          return last;
        }
        return Math.min(last, i + 1);
      });
    }, 140 / speed);
    return () => clearInterval(timer.current);
  }, [playing, speed, result, last]);

  const dispatch = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await post("/api/shipments/simulate", {
        product,
        origin_id: origin,
        destination_city: city,
        vehicle,
        packed_hours_ago: packed,
        printed_expiry_days: printed,
        planned_outlet_id: plannedValid || null,
        incidents: incidents.filter((i) => i.on).map(({ type, at_h, minutes }) => ({ type, at_h, minutes })),
      });
      setResult(r);
      setIdx(0);
      setPlaying(true);
      setShowRejected(false);
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(false);
  };

  const now = result?.timeline[idx];
  const arrived = !!result && idx >= last;
  const visible = useMemo(() => (result ? result.timeline.slice(0, idx + 1) : []), [result, idx]);
  const shocksSoFar = result ? result.events.filter((e: any) => e.type === "shock" && e.minute <= now.minute) : [];
  const eventsSoFar = result ? result.events.filter((e: any) => e.minute <= now.minute).reverse() : [];
  const totalMin = result ? result.timeline[last].minute : 1;
  const sh = result?.shipment;

  return (
    <div className="ship-layout">
      {/* ---------------- form ---------------- */}
      <section className="panel ship-form">
        <div className="panel-heading">
          <div>
            <h2>New shipment</h2>
            <p>Product, label and route. The crate tag senses the rest.</p>
          </div>
          <span className="subtle-tag">Input</span>
        </div>
        {!opts ? (
          <p className="ship-muted">{error ?? "Loading options…"}</p>
        ) : (
          <>
            <div className="ship-presets">
              <span>Demo presets</span>
              {PRESETS.map((pr) => (
                <button key={pr.id} onClick={() => applyPreset(pr)} title={pr.detail}>
                  {pr.label}
                </button>
              ))}
            </div>
            <div className="ship-products">
              {Object.values(opts.products as Record<string, any>).map((p) => (
                <button
                  key={p.id}
                  className={product === p.id ? "selected" : ""}
                  onClick={() => setProduct(p.id)}
                  title={`FoodKeeper fridge: ${p.foodkeeper_fridge_days.join("–")} days`}
                >
                  <Icon name={PRODUCT_ICONS[p.id]} size={16} />
                  {p.label.replace(" (curd/yogurt)", "")}
                </button>
              ))}
            </div>
            <div className="ship-fields">
              <Field label="Packed / harvested">
                <Range value={packed} min={0} max={120} step={2} onChange={setPacked} unit="h ago" />
              </Field>
              <Field label="Printed expiry (label)">
                <Range value={printed} min={1} max={30} step={1} onChange={setPrinted} unit="days" />
              </Field>
              <Field label="Origin">
                <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
                  {originsForProduct.map((o: any) => (
                    <option key={o.id} value={o.id}>
                      {o.name}, {o.state}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Destination city">
                <select value={city} onChange={(e) => setCity(e.target.value)}>
                  {opts.cities.map((c: any) => (
                    <option key={c.id} value={c.id}>
                      {c.name} · {c.warehouse.area} warehouse
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Planned outlet (optional)">
                <select value={plannedValid} onChange={(e) => setPlanned(e.target.value)}>
                  <option value="">Let FreshSense choose</option>
                  {cityObj?.outlets
                    .filter((l: any) => l.type !== "food_bank")
                    .map((l: any) => (
                      <option key={l.id} value={l.id}>
                        {l.name.replace(" (demo)", "")}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Vehicle">
                <div className="ship-segment">
                  {opts.vehicles.map((v: any) => (
                    <button key={v.id} className={vehicle === v.id ? "selected" : ""} onClick={() => setVehicle(v.id)} title={v.detail}>
                      {v.label}
                    </button>
                  ))}
                </div>
              </Field>
            </div>
            <div className="ship-subhead">Disruptions on the way</div>
            <div className="ship-incidents">
              {incidents.map((inc, i) => {
                const meta = opts.incidents.find((m: any) => m.id === inc.type);
                const set = (patch: Partial<Incident>) =>
                  setIncidents((all) => all.map((x, j) => (j === i ? { ...x, ...patch } : x)));
                return (
                  <div key={inc.type} className={`ship-incident ${inc.on ? "on" : ""}`}>
                    <label className="ship-incident-head">
                      <input type="checkbox" checked={inc.on} onChange={(e) => set({ on: e.target.checked })} />
                      <span>
                        <b>{meta.label}</b>
                        <small>{meta.detail}</small>
                      </span>
                    </label>
                    {inc.on && (
                      <div className="ship-incident-params">
                        {inc.type !== "dock" && (
                          <Range value={inc.at_h} min={0} max={24} step={0.5} onChange={(v) => set({ at_h: v })} unit="h into trip" />
                        )}
                        {(inc.type === "compressor" || inc.type === "dock") && (
                          <Range value={inc.minutes} min={15} max={480} step={15} onChange={(v) => set({ minutes: v })} unit="min" />
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <button className="heat-button ship-go" disabled={busy} onClick={dispatch}>
              <Icon name="truck" size={16} />
              {busy ? "Dispatching…" : "Dispatch shipment"}
            </button>
            {error && <p className="testlab-error">{error}</p>}
          </>
        )}
      </section>

      {/* ---------------- journey ---------------- */}
      <div className="ship-main">
        {!result ? (
          <section className="panel ship-empty">
            <span className="product-icon brand-icon">
              <Icon name="route" size={24} />
            </span>
            <h3>Choose a product and route, then dispatch</h3>
            <p>
              The tag records temperature, humidity and shocks for the whole trip (replayed from real cold-chain and
              accelerometer data). At the destination warehouse, FreshSense lists every outlet that can still accept
              the crate and routes it to the best one.
            </p>
          </section>
        ) : (
          <>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">
                    <span />
                    {sh.emoji} {sh.product_label.toUpperCase()} · {sh.distance_km} KM · {sh.total_h} H
                  </div>
                  <h2>
                    {sh.origin.name} → {sh.city.name}
                  </h2>
                  <p>
                    {sh.vehicle === "reefer" ? "Reefer truck" : "Insulated van"} · temperature from {sh.temperature_source}
                  </p>
                </div>
                <div className="ship-playback">
                  <button className="icon-button" aria-label={playing ? "Pause" : "Play"} onClick={() => (idx >= last ? (setIdx(0), setPlaying(true)) : setPlaying(!playing))}>
                    <Icon name={playing ? "pause" : idx >= last ? "reset" : "play"} size={15} />
                  </button>
                  <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Playback speed">
                    {[1, 2, 4, 8].map((s) => (
                      <option key={s} value={s}>
                        {s}×
                      </option>
                    ))}
                  </select>
                  <button className="text-button" onClick={() => (setIdx(last), setPlaying(false))}>
                    Skip to arrival
                  </button>
                </div>
              </div>

              <div className="route-track">
                <div className="route-line">
                  <i style={{ width: `${(now.minute / totalMin) * 100}%` }} />
                </div>
                <span className="route-truck" style={{ left: `${(now.minute / totalMin) * 100}%` }}>
                  <Icon name="truck" size={16} />
                </span>
                {[
                  { at: 0, label: sh.origin.name, sub: "Origin" },
                  { at: (30 / totalMin) * 100, label: "Highway", sub: `${sh.distance_km} km` },
                  { at: ((totalMin - 30 - (result.arrival ? 0 : 0)) / totalMin) * 100, label: sh.warehouse.area, sub: "Hyperpure warehouse" },
                ].map((n, i) => (
                  <div key={i} className={`route-node ${now.minute / totalMin * 100 >= n.at ? "done" : ""}`} style={{ left: `${n.at}%` }}>
                    <i />
                    <b>{n.label}</b>
                    <small>{n.sub}</small>
                  </div>
                ))}
              </div>
              <input
                className="ship-scrub"
                type="range"
                min={0}
                max={last}
                value={idx}
                onChange={(e) => (setIdx(Number(e.target.value)), setPlaying(false))}
                aria-label="Journey time"
              />
              <div className="ship-clock">
                <span>
                  <Icon name="clock" size={13} /> {hm(now.minute)} into trip ·{" "}
                  {new Date(now.ts).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" })}
                </span>
                <b>{STAGE_LABEL[now.stage]}</b>
              </div>

              <div className="sensor-grid">
                <Sensor icon="temp" label="Temperature" value={`${number(now.temp_c)}°C`} alert={now.temp_c > sh.safe_temp_c} note={`safe ≤ ${sh.safe_temp_c}°C`} />
                <Sensor icon="drop" label="Humidity" value={`${number(now.humidity, 0)}%`} note="tag DHT22-class sensor" />
                <Sensor
                  icon="shock"
                  label="Shocks"
                  value={String(shocksSoFar.length)}
                  alert={now.shock_g > 0}
                  note={now.shock_g > 0 ? `${number(now.shock_g, 2)} g peak now` : shocksSoFar.length ? shocksSoFar[shocksSoFar.length - 1].title : "none yet"}
                />
                <Sensor icon="activity" label="Bacterial load" value={`${number(now.tvc, 2)} log`} note={statusInfo(now.status).label} status={now.status} />
                <Sensor icon="clock" label="Shelf life left" value={`${number(now.hours_left, 0)}h`} note={`at ${sh.reference_temp_c}°C`} status={now.status} />
              </div>
            </section>

            <div className="ship-row">
              <section className="panel ship-chart-panel">
                <div className="panel-heading">
                  <div>
                    <h2>What the tag sensed</h2>
                    <p>Temperature (red) and bacterial load (dark) · dashed: safe limit</p>
                  </div>
                </div>
                <div className="ship-chart">
                  <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                    <LineChart data={visible} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                      <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
                      <XAxis dataKey="minute" type="number" domain={[0, totalMin]} tickFormatter={(m) => `${Math.round(m / 60)}h`} tick={{ fontSize: 9, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
                      <YAxis yAxisId="t" domain={[-2, (max: number) => Math.max(sh.safe_temp_c + 6, Math.ceil(max + 1))]} tick={{ fontSize: 9, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
                      <YAxis yAxisId="b" orientation="right" domain={[1.5, (max: number) => Math.max(5.6, Math.ceil(max * 2) / 2)]} tick={{ fontSize: 9, fill: "var(--muted)" }} tickLine={false} axisLine={false} width={30} />
                      <Tooltip
                        labelFormatter={(m) => hm(Number(m))}
                        contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 11 }}
                      />
                      <ReferenceLine yAxisId="t" y={sh.safe_temp_c} stroke="var(--brand)" strokeDasharray="4 4" />
                      <ReferenceLine yAxisId="b" y={sh.thresholds_log_cfu[2]} stroke="var(--muted)" strokeDasharray="2 4" />
                      <Line yAxisId="t" type="monotone" dataKey="temp_c" name="Temp °C" stroke="var(--brand)" strokeWidth={2} dot={false} isAnimationActive={false} />
                      <Line yAxisId="b" type="monotone" dataKey="tvc" name="Bacteria (log CFU/g)" stroke="var(--ink)" strokeWidth={1.6} dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>
              <section className="panel ship-events">
                <div className="panel-heading">
                  <div>
                    <h2>Tag log</h2>
                    <p>{eventsSoFar.length} events so far</p>
                  </div>
                </div>
                <ul>
                  {eventsSoFar.map((e: any, i: number) => (
                    <li key={`${e.minute}-${i}`} className={`sev-${e.severity}`}>
                      <span>{hm(e.minute)}</span>
                      <div>
                        <b>{e.title}</b>
                        <small>{e.detail}</small>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            {arrived && <Arrival result={result} showRejected={showRejected} setShowRejected={setShowRejected} />}
          </>
        )}
      </div>
    </div>
  );
}

function Arrival({ result, showRejected, setShowRejected }: { result: any; showRejected: boolean; setShowRejected: (v: boolean) => void }) {
  const { arrival: a, decision: d, shipment: sh, candidates } = result;
  const s = statusInfo(a.status);
  const rows = candidates.filter((c: any) => showRejected || c.accepts);
  const labelDiff = a.label_hours_left == null ? null : a.hours_left - a.label_hours_left;
  return (
    <section className="panel ship-arrival">
      <div className="panel-heading">
        <div>
          <div className="eyebrow">
            <span />
            ARRIVED · {sh.warehouse.name.toUpperCase()}
          </div>
          <h2>
            {DECISION_TEXT[d.decision]}
            {d.location ? ` → ${d.location.name.replace(" (demo)", "")}` : ""}
          </h2>
          <p>{d.reason}</p>
        </div>
        <span className={`status status-${a.status}`} style={{ "--status-color": s.color } as CSSProperties}>
          <i />
          {s.label}
        </span>
      </div>
      <div className="ship-verdict">
        <div>
          <small>Printed label says</small>
          <strong>{a.label_hours_left == null ? "—" : `${number(a.label_hours_left, 0)}h`}</strong>
          <span>left</span>
        </div>
        <div className="real">
          <small>FreshSense says</small>
          <strong>{number(a.hours_left, 0)}h</strong>
          <span>at {sh.reference_temp_c}°C · {a.stage}</span>
        </div>
        <div>
          <small>Difference</small>
          <strong className={labelDiff != null && labelDiff < 0 ? "neg" : ""}>
            {labelDiff == null ? "—" : `${labelDiff > 0 ? "+" : ""}${number(labelDiff, 0)}h`}
          </strong>
          <span>{labelDiff != null && labelDiff < 0 ? "label overstates freshness" : "real vs label"}</span>
        </div>
        <div>
          <small>On the way</small>
          <strong>{number(a.extra_life_lost_h)}h</strong>
          <span>lost to heat · {a.minutes_above_safe} min above {sh.safe_temp_c}°C · {a.shocks} shocks</span>
        </div>
      </div>
      <div className="ship-match">
        <OutletMap result={result} />
        <div className="ship-match-table">
          <div className="ship-match-head">
            <b>
              {d.accepting} of {d.total} outlets in {sh.city.name} accept this crate
            </b>
            <button className="text-button" onClick={() => setShowRejected(!showRejected)}>
              {showRejected ? "Hide rejected" : "Show rejected"}
            </button>
          </div>
          <div className="table-scroll">
            <table className="stage-table">
              <thead>
                <tr>
                  <th>OUTLET</th>
                  <th>TRAVEL</th>
                  <th>LEFT ON ARRIVAL</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((c: any) => (
                  <tr key={c.location_id} className={c.chosen ? "chosen" : c.accepts ? "" : "rejected"} title={c.reason}>
                    <td>
                      <span className="table-product">
                        <Icon name={NETWORK_ICON[c.type]} size={14} />
                      </span>
                      <b>{c.area}</b>
                      <small className="stage-location">{NETWORK_LABEL[c.type]}</small>
                    </td>
                    <td>{c.travel_min} min</td>
                    <td>
                      {number(c.hours_on_arrival, 0)}h <small className="stage-location">needs ≥ {c.min_hours_needed}h</small>
                    </td>
                    <td>
                      {c.chosen ? (
                        <span className="arrival-status safe">
                          <Icon name="check" size={12} />
                          Routed here
                        </span>
                      ) : c.accepts ? (
                        <span className="ship-ok">Accepts</span>
                      ) : (
                        <span className="ship-no">Rejects</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length && <div className="compact-empty">No outlet in {sh.city.name} can accept this crate.</div>}
          </div>
        </div>
      </div>
    </section>
  );
}

/** Schematic of the destination city: warehouse, outlets (accepting / rejecting), and the chosen route. */
function OutletMap({ result }: { result: any }) {
  const { candidates, shipment: sh } = result;
  const pts = [...candidates, { ...sh.warehouse, wh: true }];
  const lats = pts.map((p: any) => p.lat),
    lngs = pts.map((p: any) => p.lng);
  const [a, b, c, d] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  const W = 320,
    H = 260,
    pad = 22;
  const x = (lng: number) => pad + ((lng - c) / (d - c || 1)) * (W - 2 * pad);
  const y = (lat: number) => H - pad - ((lat - a) / (b - a || 1)) * (H - 2 * pad);
  const chosen = candidates.find((k: any) => k.chosen);
  return (
    <svg className="outlet-map" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Outlets in ${sh.city.name}`}>
      <rect x="0" y="0" width={W} height={H} rx="10" fill="var(--surface-subtle)" />
      {candidates
        .filter((k: any) => k.accepts)
        .map((k: any) => (
          <line key={`l-${k.location_id}`} x1={x(sh.warehouse.lng)} y1={y(sh.warehouse.lat)} x2={x(k.lng)} y2={y(k.lat)} stroke="var(--border)" strokeWidth="1" />
        ))}
      {chosen && (
        <line x1={x(sh.warehouse.lng)} y1={y(sh.warehouse.lat)} x2={x(chosen.lng)} y2={y(chosen.lat)} stroke="var(--brand)" strokeWidth="2.5" strokeDasharray="6 4" className="route-draw" />
      )}
      {candidates.map((k: any) => (
        <g key={k.location_id}>
          <circle cx={x(k.lng)} cy={y(k.lat)} r={k.chosen ? 7 : 5} fill={k.chosen ? "var(--brand)" : k.accepts ? (k.type === "food_bank" ? "#db2777" : "#247b42") : "#c4c4c4"} stroke="#fff" strokeWidth="1.5">
            <title>
              {k.name} · {k.reason}
            </title>
          </circle>
          {k.chosen && (
            <text x={x(k.lng) + (x(k.lng) > W / 2 ? -10 : 10)} y={y(k.lat) + 4} textAnchor={x(k.lng) > W / 2 ? "end" : "start"} fontSize="10" fontWeight="600" fill="var(--ink)">
              {k.area}
            </text>
          )}
        </g>
      ))}
      <rect x={x(sh.warehouse.lng) - 7} y={y(sh.warehouse.lat) - 7} width="14" height="14" rx="3" fill="var(--ink)" />
      <text x={x(sh.warehouse.lng) + (x(sh.warehouse.lng) > W / 2 ? -10 : 10)} y={y(sh.warehouse.lat) - 10} textAnchor={x(sh.warehouse.lng) > W / 2 ? "end" : "start"} fontSize="10" fill="var(--muted)">
        Warehouse
      </text>
      <g fontSize="9" fill="var(--muted)">
        <circle cx="16" cy={H - 14} r="4" fill="#247b42" />
        <text x="24" y={H - 11}>accepts</text>
        <circle cx="72" cy={H - 14} r="4" fill="#c4c4c4" />
        <text x="80" y={H - 11}>rejects</text>
        <circle cx="128" cy={H - 14} r="4" fill="var(--brand)" />
        <text x="136" y={H - 11}>routed</text>
      </g>
    </svg>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="ship-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Range({ value, min, max, step, onChange, unit }: { value: number; min: number; max: number; step: number; onChange: (v: number) => void; unit: string }) {
  return (
    <span className="ship-range">
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <b>
        {value} <small>{unit}</small>
      </b>
    </span>
  );
}

function Sensor({ icon, label, value, note, alert, status }: { icon: IconName; label: string; value: string; note: string; alert?: boolean; status?: string }) {
  const color = status ? statusInfo(status as any).color : undefined;
  return (
    <div className={`sensor-tile ${alert ? "alert" : ""}`} style={color ? ({ "--status-color": color } as CSSProperties) : undefined}>
      <span>
        <Icon name={icon} size={14} />
        {label}
      </span>
      <strong>{value}</strong>
      <small>
        {status && <i className="sensor-dot" />}
        {note}
      </small>
    </div>
  );
}
