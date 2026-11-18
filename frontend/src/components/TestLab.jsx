import { useEffect, useState } from 'react'
import { getTestcase, getTestcases, predict, runTestcases } from '../api'
import { STATUS_COLORS } from '../config'

const SAMPLE_CSV = `minute,temp_c
0,3
120,3
240,3.5
300,12
360,18
420,9
480,4
720,3
1440,3`

const GAS_HEADERS = ['MQ2', 'MQ3', 'MQ4', 'MQ5', 'MQ135', 'MQ136']

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean)
  const head = lines[0].split(',').map((h) => h.trim())
  const iMin = head.indexOf('minute')
  if (iMin < 0) throw new Error('CSV needs a "minute" column')
  const iT = head.indexOf('temp_c')
  const iH = head.indexOf('humidity')
  const gasIdx = GAS_HEADERS.map((g) => head.indexOf(g))
  const hasGas = gasIdx.every((i) => i >= 0)
  return lines.slice(1).map((l) => {
    const c = l.split(',').map((x) => x.trim())
    const r = { minute: Number(c[iMin]) }
    if (iT >= 0 && c[iT] !== '') r.temp_c = Number(c[iT])
    if (iH >= 0 && c[iH] !== '') r.humidity = Number(c[iH])
    if (hasGas) r.gas = Object.fromEntries(GAS_HEADERS.map((g, k) => [g, Number(c[gasIdx[k]])]))
    return r
  })
}

export default function TestLab({ meta }) {
  const [cases, setCases] = useState([])
  const [run, setRun] = useState(null)
  const [busy, setBusy] = useState(false)
  const [product, setProduct] = useState('chicken')
  const [csv, setCsv] = useState(SAMPLE_CSV)
  const [initialTvc, setInitialTvc] = useState('')
  const [dest, setDest] = useState('')
  const [result, setResult] = useState(null)
  const [expected, setExpected] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    getTestcases().then(setCases).catch((e) => setErr(e.message))
  }, [])

  const products = Object.entries(meta?.products || {})
  const restaurants = (meta?.locations || []).filter((l) => l.type !== 'warehouse')

  const runAll = async () => {
    setBusy(true)
    try {
      setRun(await runTestcases())
    } catch (e) {
      setErr(e.message)
    }
    setBusy(false)
  }

  const loadCase = async (id) => {
    const c = await getTestcase(id)
    setProduct(c.input.product)
    setInitialTvc(c.input.initial_tvc ?? '')
    const withGas = c.input.readings[0]?.gas
    const head = ['minute', 'temp_c', ...(withGas ? GAS_HEADERS : [])]
    const rows = c.input.readings.map((r) => [r.minute, r.temp_c ?? '', ...(withGas ? GAS_HEADERS.map((g) => r.gas[g]) : [])].join(','))
    setCsv([head.join(','), ...rows].join('\n'))
    setExpected({ id: c.id, ...c.expected })
    setResult(null)
  }

  const doPredict = async () => {
    setErr(null)
    try {
      const body = { product, readings: parseCsv(csv) }
      if (initialTvc !== '') body.initial_tvc = Number(initialTvc)
      if (dest) {
        body.destination_id = dest
        body.location = { lat: 13.0707, lng: 77.7982 } // from the Hoskote warehouse
      }
      setResult(await predict(body))
    } catch (e) {
      setErr(e.message)
    }
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="grid gap-4 xl:grid-cols-2">
        {/* left: custom input */}
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="font-bold">Try the model with your own readings</div>
          <div className="mb-2 text-[11px] text-gray-500">
            CSV columns: <code>minute</code> (since packing), <code>temp_c</code>, optional <code>humidity</code>, optional gas sensors{' '}
            <code>{GAS_HEADERS.join(', ')}</code> (meat only, at least 30 minutes). Or load a held-out case on the right.
          </div>
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
            <label>
              Product{' '}
              <select className="rounded border px-1 py-0.5" value={product} onChange={(e) => setProduct(e.target.value)}>
                {products.map(([k, p]) => (
                  <option key={k} value={k}>
                    {p.emoji} {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Start load (log CFU/g){' '}
              <input className="w-20 rounded border px-1 py-0.5" placeholder="median" value={initialTvc} onChange={(e) => setInitialTvc(e.target.value)} />
            </label>
            <label>
              Planned stop{' '}
              <select className="rounded border px-1 py-0.5" value={dest} onChange={(e) => setDest(e.target.value)}>
                <option value="">(none)</option>
                {restaurants.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name.replace(' (demo)', '')}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <textarea className="h-56 w-full rounded border p-2 font-mono text-[11px]" value={csv} onChange={(e) => setCsv(e.target.value)} />
          <button className="mt-2 rounded-md bg-[#E23744] px-4 py-1.5 text-sm font-semibold text-white" onClick={doPredict}>
            Predict freshness
          </button>
          {err && <div className="mt-2 text-xs text-red-600">{err}</div>}
          {result && <Result r={result} expected={expected} />}
        </div>

        {/* right: held-out cases */}
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="flex items-center">
            <div>
              <div className="font-bold">Held-out test cases (real lab data)</div>
              <div className="text-[11px] text-gray-500">Beef series never used for fitting. Expected = the lab’s measured bacterial count.</div>
            </div>
            <button className="ml-auto rounded-md bg-gray-900 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50" disabled={busy} onClick={runAll}>
              {busy ? 'Running…' : '▶ Run all'}
            </button>
          </div>
          {run && (
            <div className="mt-2 rounded bg-green-50 p-2 text-sm font-semibold text-green-800">
              {run.passed}/{run.total} passed · mean error {run.mean_abs_error_log_cfu} log CFU/g
            </div>
          )}
          <table className="mt-2 w-full text-[11px]">
            <thead className="text-left text-gray-400">
              <tr>
                <th>Case</th>
                <th className="text-right">Expected</th>
                <th className="text-right">Predicted</th>
                <th className="text-right">Error</th>
                <th className="pl-2">Stage</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => {
                const r = run?.results.find((x) => x.id === c.id)
                return (
                  <tr key={c.id} className="border-t">
                    <td className="py-1">{c.id}</td>
                    <td className="text-right">{c.expected.tvc_log_cfu}</td>
                    <td className="text-right">{r ? r.predicted_tvc : '–'}</td>
                    <td className="text-right">{r ? r.abs_error : '–'}</td>
                    <td className="pl-2">
                      {c.expected.stage}
                      {r && ` → ${r.predicted_stage}`} {r && (r.pass ? '✅' : '❌')}
                    </td>
                    <td>
                      <button className="rounded border px-1.5 py-0.5 hover:bg-gray-50" onClick={() => loadCase(c.id)}>
                        Load
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Result({ r, expected }) {
  const rows = [
    ['Bacterial load (fused)', `${r.tvc_estimate_log_cfu} log CFU/g`],
    ['…from temperature model', `${r.tvc_kinetic_log_cfu}`],
    ['…from gas sensors', r.tvc_gas_log_cfu ?? 'not used'],
    ['Quality stage', r.quality_stage],
    ['Freshness score', r.freshness_score],
    [`Hours left at ${r.reference_temp_c} °C`, `${r.hours_left_at_reference_temp} h`],
    [`Hours left if it stays at ${r.last_temp_c} °C`, `${r.hours_left_if_temperature_stays} h`],
    [`Minutes above ${r.safe_temp_c} °C`, r.minutes_above_safe_temp],
    ['Extra life lost to heat', `${r.extra_life_lost_to_heat_h} h`],
    ['Temperature', r.temperature_source],
  ]
  return (
    <div className="mt-3 rounded-lg border p-3 text-xs">
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-white" style={{ background: STATUS_COLORS[r.status] }}>
          {r.status}
        </span>
        <b>{r.product_label}</b>
        <span className="text-gray-500">· {Math.round(r.minutes_covered)} min of readings</span>
      </div>
      <table className="w-full">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-t">
              <td className="py-0.5 text-gray-500">{k}</td>
              <td className="text-right font-semibold">{String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {r.recommendation && (
        <div className="mt-2 rounded bg-orange-50 p-2">
          <b>{r.recommendation.decision}</b> → {r.recommendation.location_name || '—'} ({r.recommendation.travel_min} min)
          <div className="text-gray-600">{r.recommendation.reason}</div>
        </div>
      )}
      {expected && (
        <div className="mt-2 rounded bg-blue-50 p-2">
          <b>Expected ({expected.id}):</b> {expected.tvc_log_cfu} log CFU/g, stage “{expected.stage}”
          {expected.hours_until_spoiled_at_same_conditions != null && `, spoiled ${expected.hours_until_spoiled_at_same_conditions} h later in the lab`} ·
          error {Math.abs(r.tvc_estimate_log_cfu - expected.tvc_log_cfu).toFixed(2)}
        </div>
      )}
      {r.notes?.map((n) => (
        <div key={n} className="mt-1 text-amber-700">
          ⚠ {n}
        </div>
      ))}
    </div>
  )
}
