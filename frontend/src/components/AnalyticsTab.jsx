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
        <Card title="Where freshness is lost: by truck" note="Extra shelf-life hours lost to heat. Last 7 days (demo data) + live.">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trucks} layout="vertical" margin={{ left: 20, right: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis type="number" tick={{ fontSize: 11 }} unit=" h" />
              <YAxis type="category" dataKey="label" width={150} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v, n) => (n === 'extra_loss_h' ? [`${v} h`, 'Extra loss'] : [v, n])} contentStyle={{ fontSize: 11 }} />
              <Bar dataKey="extra_loss_h" radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, formatter: (v) => `${v} h` }}>
                {trucks.map((t) => (
                  <Cell key={t.truck_id} fill={colorOf[t.truck_id] || '#6B7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="text-xs text-gray-600">
            🚨 <b>{trucks[0]?.name}</b> ({trucks[0]?.driver}) has the most heat damage, with {trucks[0]?.excursions} excursions. That makes it the first truck to inspect.
          </div>
        </Card>

        <Card title="Where freshness is lost: by stage" note="Extra hours lost, all crates since reset">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={a.hours_lost_by_stage} margin={{ right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit=" h" />
              <Tooltip formatter={(v) => [`${v} h`, 'Extra loss']} contentStyle={{ fontSize: 11 }} />
              <Bar dataKey="extra_loss_h" fill="#E23744" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="FIFO vs FreshSense: benchmark" note="Simulation with literature-based parameters, not field data">
          {a.benchmark ? <Benchmark b={a.benchmark} /> : <Pending text="Benchmark pending. Run python benchmark.py in backend/." />}
        </Card>

        <Card title="Model 1: spoilage from gas sensors" note="Validated on REAL lab data">
          {a.model_card?.available ? <ModelCard m={a.model_card} /> : <Pending text="Model results pending (Person C)." />}
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
          {b.crates_simulated} crates simulated
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
              <Bar dataKey="FIFO" fill="#9CA3AF" radius={[4, 4, 0, 0]} label={{ position: 'top', fontSize: 11 }} />
              <Bar dataKey="FreshSense" fill="#16A34A" radius={[4, 4, 0, 0]} label={{ position: 'top', fontSize: 11 }} />
            </BarChart>
          </ResponsiveContainer>
        ))}
      </div>
    </div>
  )
}

function ModelCard({ m }) {
  return (
    <div className="text-xs">
      <a href={m.dataset_url} target="_blank" rel="noreferrer" className="font-semibold text-blue-700 underline">
        {m.dataset_name}
      </a>
      <div className="mt-0.5 text-gray-600">{m.task}</div>
      <div className="mt-2 flex gap-6">
        <div>
          <div className="text-3xl font-bold">{Math.round(m.accuracy * 100)}%</div>
          <div className="text-gray-500">
            exact stage (of 4)
            {m.chance_accuracy != null && <div>chance = {Math.round(m.chance_accuracy * 100)}%</div>}
          </div>
        </div>
        {m.within_one_stage != null && (
          <div>
            <div className="text-3xl font-bold text-green-600">{Math.round(m.within_one_stage * 100)}%</div>
            <div className="text-gray-500">within one stage</div>
          </div>
        )}
        {m.binary_accuracy != null && (
          <div>
            <div className="text-3xl font-bold">{Math.round(m.binary_accuracy * 100)}%</div>
            <div className="text-gray-500">spoiled vs sellable</div>
          </div>
        )}
      </div>
      <div className="mt-2 text-gray-500">
        {m.n_samples} samples · {m.n_features} features · macro F1 {m.macro_f1} · top sensors: {m.top_features?.join(', ')}
        <br />
        Tested on beef cuts the model never saw ({m.validation}).
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2">
        {(m.images || []).map((src) => (
          <img key={src} src={src} alt="" className="rounded border" onError={(e) => (e.currentTarget.style.display = 'none')} />
        ))}
      </div>
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
