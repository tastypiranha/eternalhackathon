import { useEffect, useRef } from 'react'
import { ALERT_ICONS, DECISION_STYLE, SEVERITY_COLORS, STATUS_COLORS, areaOf, fmtH, fmtTime } from '../config'

const SKIP_ALERT_TYPES = new Set(['rerouted', 'donated', 'discarded'])

export function EventFeed({ state, locations, onOpenCrate }) {
  const items = [
    ...(state?.redirects || []).map((r) => ({ kind: 'redirect', ts: r.ts, id: r.id, r })),
    ...(state?.alerts || []).filter((a) => !SKIP_ALERT_TYPES.has(a.type)).map((a) => ({ kind: 'alert', ts: a.ts, id: a.id, a })),
  ]
    .sort((x, y) => (x.ts < y.ts ? 1 : x.ts > y.ts ? -1 : y.id.localeCompare(x.id, undefined, { numeric: true })))
    .slice(0, 25)

  return (
    <div className="flex h-full flex-col">
      <h3 className="px-3 pb-1 pt-2 text-xs font-bold uppercase tracking-wide text-gray-500">Live redirects & alerts</h3>
      <div className="flex-1 space-y-1.5 overflow-y-auto px-3 pb-2">
        {items.length === 0 && (
          <div className="rounded border border-dashed p-3 text-center text-xs text-gray-400">
            No events yet. Press ▶ Resume, then try 🔥 Heat crate.
          </div>
        )}
        {items.map((it) =>
          it.kind === 'redirect' ? (
            <RedirectCard key={it.id} r={it.r} locations={locations} onOpenCrate={onOpenCrate} />
          ) : (
            <AlertRow key={it.id} a={it.a} onOpenCrate={onOpenCrate} />
          ),
        )}
      </div>
    </div>
  )
}

function RedirectCard({ r, locations, onOpenCrate }) {
  const st = DECISION_STYLE[r.decision] || DECISION_STYLE.REDIRECT
  const to = r.to_location_id ? locations?.[r.to_location_id]?.name : 'Discarded'
  return (
    <button
      onClick={() => onOpenCrate(r.crate_id)}
      className={`w-full rounded-lg border ${st.border} ${st.bg} p-2 text-left text-xs hover:brightness-95`}
    >
      <div className="flex items-center gap-1 font-semibold">
        <span>{st.icon}</span>
        <span>
          {r.crate_id} {r.decision === 'DONATE' ? 'donated' : r.decision === 'DISCARD' ? 'discarded' : 'rerouted'}
          {r.to_location_id && ' → '}
          {to}
        </span>
        <span className="ml-auto font-normal text-gray-500">{fmtTime(r.ts)}</span>
      </div>
      <div className="mt-0.5 text-[11px] leading-snug text-gray-700">{r.reason}</div>
      {r.decision !== 'DISCARD' && (
        <div className="mt-0.5 text-[11px] font-semibold text-green-700">
          {r.kg_saved} kg saved · {r.travel_min} min away · was going to {areaOf(locations, r.from_location_id)}
        </div>
      )}
    </button>
  )
}

function AlertRow({ a, onOpenCrate }) {
  return (
    <div
      onClick={() => a.crate_id && onOpenCrate(a.crate_id)}
      className={`flex items-start gap-1.5 rounded border-l-4 bg-white px-2 py-1 text-[11px] shadow-sm ${a.crate_id ? 'cursor-pointer hover:bg-gray-50' : ''}`}
      style={{ borderLeftColor: SEVERITY_COLORS[a.severity] }}
    >
      <span>{ALERT_ICONS[a.type] || '•'}</span>
      <span className="text-gray-500">{fmtTime(a.ts)}</span>
      <span className="flex-1">{a.message}</span>
    </div>
  )
}

function useRankFlash(rows) {
  const prev = useRef({})
  const flashed = {}
  rows.forEach((r) => {
    const before = prev.current[r.crate_id]
    if (before !== undefined && before !== r.rank) flashed[r.crate_id] = true
  })
  useEffect(() => {
    const m = {}
    rows.forEach((r) => (m[r.crate_id] = r.rank))
    prev.current = m
  })
  return flashed
}

export function DispatchTables({ state, locations, onOpenCrate }) {
  const fifo = state?.dispatch?.fifo || []
  const fefo = state?.dispatch?.fefo || []
  const byId = Object.fromEntries((state?.crates || []).map((c) => [c.id, c]))
  const fifoFlash = useRankFlash(fifo)
  const fefoFlash = useRankFlash(fefo)
  const fifoRejects = fifo.filter((r) => r.would_be_rejected).length
  const fefoRejects = fefo.filter((r) => !r.feasible).length

  return (
    <div className="flex h-full flex-col">
      <h3 className="px-3 pb-1 pt-2 text-xs font-bold uppercase tracking-wide text-gray-500">Dispatch order</h3>
      <div className="grid flex-1 grid-cols-2 gap-2 overflow-y-auto px-3">
        <Table
          title="Old way: FIFO"
          subtitle="first in, first out"
          rows={fifo}
          byId={byId}
          locations={locations}
          flash={fifoFlash}
          onOpenCrate={onOpenCrate}
          mode="fifo"
        />
        <Table
          title="FreshSense: FEFO"
          subtitle="first to expire, first out"
          rows={fefo}
          byId={byId}
          locations={locations}
          flash={fefoFlash}
          onOpenCrate={onOpenCrate}
          mode="fefo"
        />
      </div>
      <div className="border-t px-3 py-1.5 text-[11px] font-semibold">
        <span className="text-red-600">FIFO would reject {fifoRejects} crate{fifoRejects === 1 ? '' : 's'}</span>
        <span className="text-gray-400"> · </span>
        <span className="text-green-700">FreshSense: {fefoRejects}</span>
      </div>
    </div>
  )
}

function Table({ title, subtitle, rows, byId, locations, flash, onOpenCrate, mode }) {
  return (
    <div className="min-w-0">
      <div className={`text-xs font-bold ${mode === 'fifo' ? 'text-gray-600' : 'text-[#E23744]'}`}>{title}</div>
      <div className="mb-1 text-[10px] text-gray-400">{subtitle}</div>
      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-left text-gray-400">
            <th className="w-4">#</th>
            <th>Crate</th>
            <th className="text-right">Left</th>
            <th className="pl-1">To</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const c = byId[r.crate_id]
            const bad = mode === 'fifo' && r.would_be_rejected
            return (
              <tr
                key={`${r.crate_id}-${r.rank}`}
                onClick={() => onOpenCrate(r.crate_id)}
                className={`cursor-pointer border-t border-gray-100 hover:bg-gray-50 ${bad ? 'bg-red-50' : ''} ${flash[r.crate_id] ? 'flash-row' : ''}`}
              >
                <td className="text-gray-400">{r.rank}</td>
                <td className="whitespace-nowrap">
                  {c?.emoji} {r.crate_id}
                  {mode === 'fefo' && c?.redirected && ' 🔄'}
                </td>
                <td className="text-right font-semibold" style={{ color: STATUS_COLORS[c?.status] }}>
                  {fmtH(r.hours_left)}
                </td>
                <td className="truncate pl-1 text-gray-600">
                  {areaOf(locations, r.destination_id)}
                  {bad && <span className="ml-0.5 text-red-600">❌</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
