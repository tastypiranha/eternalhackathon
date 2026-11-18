import { useEffect, useState } from "react";
import { API_BASE, LOCATIONS, PRODUCTS, number, statusInfo } from "../demo/config";
import { Icon } from "./Icon";

const GAS = ["MQ2", "MQ3", "MQ4", "MQ5", "MQ135", "MQ136"];
const SAMPLE = `minute,temp_c
0,3
120,3
240,3.5
300,12
360,18
420,9
480,4
720,3
1440,3`;

const post = (path: string, body?: unknown) =>
  fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(async (r) => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    return data;
  });

function parseCsv(text: string) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  const head = lines[0].split(",").map((h) => h.trim());
  const iMin = head.indexOf("minute");
  if (iMin < 0) throw new Error('CSV needs a "minute" column');
  const iT = head.indexOf("temp_c"),
    iH = head.indexOf("humidity");
  const gi = GAS.map((g) => head.indexOf(g));
  const hasGas = gi.every((i) => i >= 0);
  return lines.slice(1).map((line) => {
    const c = line.split(",").map((x) => x.trim());
    const r: Record<string, unknown> = { minute: Number(c[iMin]) };
    if (iT >= 0 && c[iT] !== "") r.temp_c = Number(c[iT]);
    if (iH >= 0 && c[iH] !== "") r.humidity = Number(c[iH]);
    if (hasGas) r.gas = Object.fromEntries(GAS.map((g, k) => [g, Number(c[gi[k]])]));
    return r;
  });
}

export function TestLab() {
  const [cases, setCases] = useState<any[]>([]);
  const [run, setRun] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [product, setProduct] = useState("chicken");
  const [csv, setCsv] = useState(SAMPLE);
  const [initial, setInitial] = useState("");
  const [dest, setDest] = useState("");
  const [result, setResult] = useState<any>(null);
  const [expected, setExpected] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(API_BASE + "/api/testcases")
      .then((r) => r.json())
      .then(setCases)
      .catch((e) => setError(e.message));
  }, []);

  const runAll = async () => {
    setBusy(true);
    try {
      setRun(await post("/api/testcases/run"));
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(false);
  };
  const load = async (id: string) => {
    const c = await fetch(`${API_BASE}/api/testcases/${id}`).then((r) => r.json());
    setProduct(c.input.product);
    setInitial(c.input.initial_tvc ?? "");
    const withGas = !!c.input.readings[0]?.gas;
    const head = ["minute", "temp_c", ...(withGas ? GAS : [])];
    const rows = c.input.readings.map((r: any) =>
      [r.minute, r.temp_c ?? "", ...(withGas ? GAS.map((g) => r.gas[g]) : [])].join(","),
    );
    setCsv([head.join(","), ...rows].join("\n"));
    setExpected({ id: c.id, ...c.expected });
    setResult(null);
  };
  const predict = async () => {
    setError(null);
    try {
      const body: Record<string, unknown> = { product, readings: parseCsv(csv) };
      if (initial !== "") body.initial_tvc = Number(initial);
      if (dest) {
        body.destination_id = dest;
        const wh = LOCATIONS.find((l) => l.type === "warehouse")!;
        body.location = { lat: wh.lat, lng: wh.lng };
      }
      setResult(await post("/api/predict", body));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="analytics-page">
      <div className="analytics-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Try the model with your own readings</h2>
              <p>POST /api/predict · CSV: minute, temp_c, optional humidity and gas sensors {GAS.join(", ")} (meat only)</p>
            </div>
            <span className="subtle-tag">Live model</span>
          </div>
          <div className="testlab-form">
            <label>
              <span>Product</span>
              <select value={product} onChange={(e) => setProduct(e.target.value)}>
                {Object.values(PRODUCTS).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Start load (log CFU/g)</span>
              <input placeholder="median" value={initial} onChange={(e) => setInitial(e.target.value)} />
            </label>
            <label>
              <span>Planned stop (from warehouse)</span>
              <select value={dest} onChange={(e) => setDest(e.target.value)}>
                <option value="">None</option>
                {LOCATIONS.filter((l) => l.type !== "warehouse").map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name.replace(" (demo)", "")}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <textarea className="testlab-csv" value={csv} onChange={(e) => setCsv(e.target.value)} spellCheck={false} />
          <div className="testlab-actions">
            <button className="heat-button" onClick={predict}>
              <Icon name="play" size={14} />
              Predict freshness
            </button>
            {error && <span className="testlab-error">{error}</span>}
          </div>
          {result && <Result r={result} expected={expected} />}
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Held-out test cases</h2>
              <p>Real beef spoilage series never used for fitting · click a case to load it</p>
            </div>
            <button className="text-button" disabled={busy} onClick={runAll}>
              {busy ? "Running…" : "Run all"}
              <Icon name="arrow" size={14} />
            </button>
          </div>
          {run && (
            <div className="analytics-insight">
              <Icon name="check" size={18} />
              <span>
                <strong>
                  {run.passed}/{run.total} passed
                </strong>{" "}
                · mean error {number(run.mean_abs_error_log_cfu, 2)} log CFU/g (pass: ≤ 0.6 and same or
                neighbouring stage)
              </span>
            </div>
          )}
          <div className="table-scroll">
            <table className="stage-table">
              <thead>
                <tr>
                  <th>CASE</th>
                  <th>EXPECTED</th>
                  <th>PREDICTED</th>
                  <th>ERROR</th>
                  <th>STAGE</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => {
                  const r = run?.results.find((x: any) => x.id === c.id);
                  return (
                    <tr key={c.id}>
                      <td>
                        <button className="text-button" title="Load this case into the form" onClick={() => load(c.id)}>
                          {c.id}
                        </button>
                      </td>
                      <td>{number(c.expected.tvc_log_cfu, 2)}</td>
                      <td>{r ? number(r.predicted_tvc, 2) : "—"}</td>
                      <td>{r ? number(r.abs_error, 2) : "—"}</td>
                      <td>
                        {c.expected.stage}
                        {r && ` → ${r.predicted_stage}`} {r && (r.pass ? "✓" : "✗")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function Result({ r, expected }: { r: any; expected: any }) {
  const s = statusInfo(r.status);
  const rows: [string, string][] = [
    ["Bacterial load (fused)", `${number(r.tvc_estimate_log_cfu, 2)} log CFU/g`],
    ["From temperature model", number(r.tvc_kinetic_log_cfu, 2)],
    ["From gas sensors", r.tvc_gas_log_cfu == null ? "not used" : number(r.tvc_gas_log_cfu, 2)],
    ["Quality stage", r.quality_stage],
    ["Freshness score", `${number(r.freshness_score)}%`],
    [`Hours left at ${r.reference_temp_c}°C`, `${number(r.hours_left_at_reference_temp)}h`],
    [`Hours left if it stays at ${number(r.last_temp_c)}°C`, `${number(r.hours_left_if_temperature_stays)}h`],
    [`Minutes above ${r.safe_temp_c}°C`, number(r.minutes_above_safe_temp, 0)],
    ["Extra life lost to heat", `${number(r.extra_life_lost_to_heat_h)}h`],
    ["Temperature", r.temperature_source],
  ];
  return (
    <div className="testlab-result">
      <div className="testlab-result-head">
        <span className={`status status-${r.status}`} style={{ "--status-color": s.color } as React.CSSProperties}>
          <i />
          {s.label}
        </span>
        <b>{r.product_label}</b>
        <small>{number(r.minutes_covered / 60)} h of readings</small>
      </div>
      <table className="stage-table">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>
                <b>{v}</b>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {r.recommendation && (
        <div className="info-callout">
          <Icon name="route" />
          <div>
            <strong>
              {r.recommendation.decision} → {r.recommendation.location_name ?? "—"} ({r.recommendation.travel_min} min)
            </strong>
            <p>{r.recommendation.reason}</p>
          </div>
        </div>
      )}
      {expected && (
        <div className="blame-callout">
          <Icon name="check" size={21} />
          <div>
            <strong>Expected ({expected.id})</strong>
            <p>
              {number(expected.tvc_log_cfu, 2)} log CFU/g, stage “{expected.stage}” · error{" "}
              {number(Math.abs(r.tvc_estimate_log_cfu - expected.tvc_log_cfu), 2)}
            </p>
          </div>
        </div>
      )}
      {r.notes?.map((n: string) => (
        <p key={n} className="testlab-error">
          {n}
        </p>
      ))}
    </div>
  );
}
