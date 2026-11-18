import { useState } from 'react'
import { STATUS_COLORS, STATUS_LABELS, STATUS_ORDER, areaOf, fmtH, fmtT } from '../config'
import { FreshnessRing } from './common'

const PRODUCTS = [
  ['chicken', '🍗 Chicken'],
  ['dairy', '🥛 Dairy'],
  ['greens', '🥬 Greens'],
]

export default function CratesTab({ state, locations, onOpenCrate }) {
  const [statusF, setStatusF] = useState(null)
  const [productF, setProductF] = useState(null)
  const crates = (state?.crates || [])
    .filter((c) => !statusF || c.status === statusF)
    .filter((c) => !productF || c.product === productF)
    .sort((a, b) => a.hours_left - b.hours_left)

  const chip = (active, label, onClick, color) => (
    <button
      key={label}
      onClick={onClick}
      className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${active ? 'text-white' : 'bg-white text-gray-700'}`}
      style={active ? { background: color || '#111827', borderColor: color || '#111827' } : undefined}
    >
      {label}
    </button>
  )

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        {chip(!statusF, 'All statuses', () => setStatusF(null))}
        {STATUS_ORDER.map((s) => chip(statusF === s, STATUS_LABELS[s], () => setStatusF(statusF === s ? null : s), STATUS_COLORS[s]))}
        <span className="mx-2 h-4 w-px bg-gray-300" />
        {chip(!productF, 'All products', () => setProductF(null))}
        {PRODUCTS.map(([k, l]) => chip(productF === k, l, () => setProductF(productF === k ? null : k)))}
        <span className="ml-auto text-xs text-gray-500">{crates.length} crates · sorted by hours left</span>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
        {crates.map((c) => (
          <CrateCard key={c.id} c={c} locations={locations} onClick={() => onOpenCrate(c.id)} />
        ))}
      </div>
    </div>
  )
}

function CrateCard({ c, locations, onClick }) {
  const spoiled = c.status === 'spoiled'
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border border-l-4 bg-white p-3 text-left shadow-sm transition hover:shadow-md ${spoiled ? 'opacity-60 grayscale' : ''}`}
      style={{ borderLeftColor: STATUS_COLORS[c.status] }}
    >
      <div className="flex items-center gap-2">
        <span className="text-xl">{c.emoji}</span>
        <div className="font-bold">{c.id}</div>
        <div className="text-xs text-gray-500">{c.product_label}</div>
        <div className="ml-auto flex gap-1">
          {c.is_live_tag && <span className="rounded bg-indigo-100 px-1 text-[10px] font-bold text-indigo-700">📡 LIVE TAG</span>}
          {c.redirected && <span className="rounded bg-orange-100 px-1 text-[10px] font-bold text-orange-700">🔄 Redirected</span>}
          {spoiled && <span className="rounded bg-gray-200 px-1 text-[10px] font-bold">SPOILED</span>}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <FreshnessRing score={c.freshness_score} status={c.status} size={54} />
        <div>
          <div className="text-2xl font-bold" style={{ color: STATUS_COLORS[c.status] }}>
            {fmtH(c.hours_left)}
          </div>
          <div className="text-[11px] text-gray-500">left · {STATUS_LABELS[c.status]}</div>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1 text-[11px]">
        <div>
          🌡️ <b>{fmtT(c.temp_c)}</b>
        </div>
        <div>
          💧 <b>{c.humidity}%</b>
        </div>
        <div>
          👃 <b>{c.voc_index}</b>
        </div>
      </div>
      <div className="mt-1.5 truncate text-[11px] text-gray-600">
        {c.truck_id ? `${c.truck_id} → ${areaOf(locations, c.destination_id)}${c.eta_min != null ? ` · ${c.eta_min} min` : ''}` : 'Hyperpure Hoskote cold room'}
      </div>
    </button>
  )
}
