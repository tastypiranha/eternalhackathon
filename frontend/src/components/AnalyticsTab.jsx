import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getAnalytics } from '../api'

export default function AnalyticsTab({ trucksMeta }) {
  const [a, setA] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      getAnalytics()
        .then((d) => alive && (setA(d), setErr(null)))
        .catch((e) => alive && setErr(e.message))
    load()
    const t = setInterval(load, 5000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])

  if (!a) return <div className="p-6 text-sm text-gray-500">{err ? `Could not load analytics (${err})` : 'Loading analytics…'}</div>
  const colorOf = Object.fromEntries((trucksMeta || []).map((t) => [t.id, t.color]))
  const imp = a.impact
  const trucks = a.hours_lost_by_truck.map((t) => ({ ...t, label: `${t.name} · ${t.driver.replace(' (demo)', '')}` }))

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-4 grid grid-cols-3 gap-3 lg:grid-cols-6">
        <Tile label="Crates redirected" value={imp.crates_redirected} color="text-orange-600" />
        <Tile label="Donated (Feeding India)" value={imp.crates_donated} color="text-pink-600" />
        <Tile label="kg saved" value={imp.kg_saved} color="text-green-600" />
        <Tile label="Rejections avoided" value={imp.rejections_avoided} color="text-green-700" />
        <Tile label="Deliveries completed" value={imp.deliveries_completed} color="text-gray-800" />
        <Tile label="Deliveries rejected" value={imp.deliveries_rejected} color="text-red-600" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Where freshness is lost: by truck" note="Extra shelf-life hours lost to heat while in transit, since the last reset (live).">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trucks} layout="vertical" margin={{ left: 20, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis type="number" tick={{ fontSize: 11 }} unit=" h" />
              <YAxis type="category" dataKey="label" width={150} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v, n) => (n === 'extra_loss_h' ? [`${v} h`, 'Extra loss'] : [v, n])} contentStyle={{ fontSize: 11 }} />
              <Bar isAnimationActive={false} dataKey="extra_loss_h" radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, formatter: (v) => `${v} h` }}>
                {trucks.map((t) => (
                  <Cell key={t.truck_id} fill={colorOf[t.truck_id] || '#6B7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="text-xs text-gray-600">
            {trucks[0]?.extra_loss_h > 0 ? (
              <>
                🚨 <b>{trucks[0]?.name}</b> ({trucks[0]?.driver}) has the most heat damage, with {trucks[0]?.excursions} excursions. That makes it the first truck to inspect.
              </>
            ) : (
              'No heat damage in transit yet. Resume the simulation or trigger an incident.'
            )}
          </div>
        </Card>

        <Card title="Where freshness is lost: by stage" note="Extra hours lost, all crates since reset">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={a.hours_lost_by_stage} margin={{ right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit=" h" />
              <Tooltip formatter={(v) => [`${v} h`, 'Extra loss']} contentStyle={{ fontSize: 11 }} />
              <Bar isAnimationActive={false} dataKey="extra_loss_h" fill="#E23744" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="FIFO vs FreshSense: benchmark" note="Real cold-chain temperature traces + calibrated model; destination rules are assumptions">
          {a.benchmark ? <Benchmark b={a.benchmark} /> : <Pending text="Benchmark pending. Run python benchmark.py in backend/." />}
        </Card>

        <Card title="The freshness model (calibrated on real data)" note="Errors are on beef series the model never saw during fitting">
          {a.model_card?.available ? <ModelCard m={a.model_card} /> : <Pending text="Calibration missing: run backend/calibration/build.py" />}
        </Card>
      </div>
    </div>
  )
}

function Benchmark({ b }) {
  const charts = [
    { title: 'Rejected crates', data: [{ name: 'Rejected crates', FIFO: b.fifo.rejected, FreshSense: b.freshsense.rejected }] },
    { title: 'kg wasted', data: [{ name: 'kg wasted', FIFO: b.fifo.kg_wasted, FreshSense: b.freshsense.kg_wasted }] },
  ]
  return (
    <div>
      <div className="mb-2 flex gap-6">
        <div>
          <div className="text-3xl font-bold text-green-600">{b.rejection_reduction_pct}%</div>
          <div className="text-xs text-gray-500">fewer rejections</div>
        </div>
        <div>
          <div className="text-3xl font-bold text-green-600">{b.waste_reduction_pct}%</div>
          <div className="text-xs text-gray-500">less food wasted</div>
        </div>
        <div className="text-xs text-gray-500">
          {b.crates_simulated} crates on {b.real_temperature_traces} real shipment traces
          <br />
          {b.freshsense.redirected} redirected · {b.freshsense.donated} donated
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {charts.map((ch) => (
          <ResponsiveContainer key={ch.title} width="100%" height={170}>
            <BarChart data={ch.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar isAnimationActive={false} dataKey="FIFO" fill="#9CA3AF" radius={[4, 4, 0, 0]} label={{ position: 'top', fontSize: 11 }} />
              <Bar isAnimationActive={false} dataKey="FreshSense" fill="#16A34A" radius={[4, 4, 0, 0]} label={{ position: 'top', fontSize: 11 }} />
            </BarChart>
          </ResponsiveContainer>
        ))}
      </div>
    </div>
  )
}

function ModelCard({ m }) {
  const h = m.holdout || {}
  return (
    <div className="text-xs">
      <div className="grid grid-cols-4 gap-3">
        <Big v={m.gas_loso_mae} l="gas model error (log CFU/g), unseen beef series" />
        <Big v={`${Math.round(m.gas_within_one_stage * 100)}%`} l="gas model within one quality stage" />
        <Big v={m.fusion.fused_loso_mae_log_cfu} l="fused error (temperature + gas)" c="text-green-600" />
        <Big v={h.TS5?.fused_mae_log_cfu ?? '–'} l="fully held-out series TS5" c="text-green-600" />
      </div>
      <div className="mt-2 text-gray-600">
        Quality stages from labelled lab data: good ≥ {m.thresholds_log_cfu[0]}, acceptable ≥ {m.thresholds_log_cfu[1]}, spoiled ≥{' '}
        {m.thresholds_log_cfu[2]} log CFU/g · Ratkowsky growth fitted to {m.growth_points.length} real spoilage curves (Tmin {m.tmin_c} °C from
        literature) · fusion weights: temperature {m.fusion.weight_kinetic}, gas {m.fusion.weight_gas}
      </div>
      <table className="mt-2 w-full text-left">
        <thead className="text-gray-400">
          <tr>
            <th>Product</th>
            <th>FoodKeeper entry (fridge days)</th>
            <th className="text-right">Model shelf life at {m.reference_temp_c} °C</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(m.products).map(([k, p]) => (
            <tr key={k} className="border-t">
              <td>{p.label}</td>
              <td className="text-gray-600">
                {p.foodkeeper_entry} ({p.foodkeeper_fridge_days.join('–')} d)
              </td>
              <td className="text-right font-semibold">{p.model_shelf_life_days_at_ref} d</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 grid grid-cols-2 gap-2">
        {(m.images || []).map((src) => (
          <img key={src} src={src} alt="" className="rounded border" onError={(e) => (e.currentTarget.style.display = 'none')} />
        ))}
      </div>
    </div>
  )
}

function Big({ v, l, c = 'text-gray-900' }) {
  return (
    <div>
      <div className={`text-2xl font-bold ${c}`}>{v}</div>
      <div className="text-gray-500">{l}</div>
    </div>
  )
}

function Tile({ label, value, color }) {
  return (
    <div className="rounded-xl bg-white p-3 shadow-sm">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  )
}

function Card({ title, note, children }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <div className="mb-2">
        <div className="font-bold">{title}</div>
        {note && <div className="text-[11px] text-gray-400">{note}</div>}
      </div>
      {children}
    </div>
  )
}

function Pending({ text }) {
  return <div className="rounded border border-dashed p-6 text-center text-sm text-gray-400">{text}</div>
}
