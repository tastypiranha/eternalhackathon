import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import toast, { Toaster } from 'react-hot-toast'
import AnalyticsTab from './components/AnalyticsTab'
import ControlPanel from './components/ControlPanel'
import CratesTab from './components/CratesTab'
import JourneyDrawer from './components/JourneyDrawer'
import MapView from './components/MapView'
import { DispatchTables, EventFeed } from './components/RightPanel'
import { ALERT_ICONS, fmtTime } from './config'
import useLiveState from './hooks/useLiveState'

const CONN = {
  live: ['bg-green-500', 'Live'],
  polling: ['bg-amber-500', 'Polling'],
  offline: ['bg-red-500', 'Offline'],
  mock: ['bg-gray-400', 'Mock data'],
}

export default function App() {
  const { state, connection, meta } = useLiveState()
  const [tab, setTab] = useState('map')
  const [selected, setSelected] = useState(null)
  const locations = useMemo(() => (meta ? Object.fromEntries(meta.locations.map((l) => [l.id, l])) : null), [meta])
  const openCrate = useCallback((id) => setSelected(id), [])
  const closeCrate = useCallback(() => setSelected(null), [])

  useToasts(state, locations)

  if (!state || !locations) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="mb-2 text-3xl font-black">
            Fresh<span className="text-[#E23744]">Sense</span>
          </div>
          <div className="animate-pulse text-sm text-gray-500">Connecting to the FreshSense backend on :8000…</div>
          <div className="mt-1 text-xs text-gray-400">Connection: {CONN[connection]?.[1]}</div>
        </div>
      </div>
    )
  }

  const imp = state.impact
  return (
    <div className="flex h-full flex-col">
      <Toaster position="top-center" toastOptions={{ style: { fontSize: 13 } }} />
      {/* header */}
      <header className="flex h-14 shrink-0 items-center gap-4 border-b bg-white px-4">
        <div className="leading-tight">
          <div className="text-xl font-black">
            Fresh<span className="text-[#E23744]">Sense</span>
            <span className="ml-1 inline-block h-2 w-2 rounded-full bg-[#E23744]" />
          </div>
          <div className="text-[10px] text-gray-500">Freshness tracking for every crate in the Eternal cold chain</div>
        </div>
        <nav className="ml-4 flex gap-1">
          {[
            ['map', '🗺️ Live Map'],
            ['crates', '📦 Crates'],
            ['analytics', '📊 Analytics'],
          ].map(([k, l]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`rounded-md px-3 py-1.5 text-sm font-semibold ${tab === k ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
            >
              {l}
            </button>
          ))}
        </nav>
        <div className="ml-auto hidden items-center gap-2 text-xs lg:flex">
          <Chip>🔄 {imp.crates_redirected} redirected</Chip>
          <Chip>❤️ {imp.crates_donated} donated</Chip>
          <Chip className="text-green-700">🥗 {imp.kg_saved} kg saved</Chip>
          <Chip className="text-green-700">✅ {imp.rejections_avoided} rejections avoided</Chip>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="font-mono font-semibold">🕒 {fmtTime(state.sim_time)}</span>
          {state.paused && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-bold text-amber-800">⏸ Paused</span>}
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${CONN[connection][0]}`} />
            {CONN[connection][1]}
          </span>
        </div>
      </header>

      {/* body */}
      <main className="flex min-h-0 flex-1">
        <div className={`min-w-0 flex-1 ${tab === 'map' ? 'flex' : 'hidden'}`}>
          <div className="min-w-0 flex-1">
            <MapView state={state} locations={locations} onOpenCrate={openCrate} visible={tab === 'map'} />
          </div>
          <aside className="flex w-[34%] min-w-[340px] max-w-[520px] flex-col border-l bg-gray-50">
            <div className="min-h-0 flex-[5] border-b">
              <EventFeed state={state} locations={locations} onOpenCrate={openCrate} />
            </div>
            <div className="min-h-0 flex-[6] bg-white">
              <DispatchTables state={state} locations={locations} onOpenCrate={openCrate} />
            </div>
          </aside>
        </div>
        {tab === 'crates' && (
          <div className="min-w-0 flex-1">
            <CratesTab state={state} locations={locations} onOpenCrate={openCrate} />
          </div>
        )}
        {tab === 'analytics' && (
          <div className="min-w-0 flex-1">
            <AnalyticsTab trucksMeta={meta.trucks} />
          </div>
        )}
      </main>

      <footer className="h-16 shrink-0">
        <ControlPanel state={state} />
      </footer>

      <JourneyDrawer crateId={selected} locations={locations} onClose={closeCrate} />
    </div>
  )
}

function Chip({ children, className = '' }) {
  return <span className={`rounded-full bg-gray-100 px-2 py-0.5 font-semibold ${className}`}>{children}</span>
}

/** Toasts for new redirects and important alerts, deduped by id. */
function useToasts(state, locations) {
  const seen = useRef(new Set())
  const first = useRef(true)
  useEffect(() => {
    if (!state) return
    if (first.current) {
      // don't toast history that already existed when the page loaded
      first.current = false
      ;[...(state.alerts || []), ...(state.redirects || [])].forEach((x) => seen.current.add(x.id))
      return
    }
    for (const r of state.new_redirects || []) {
      if (seen.current.has(r.id)) continue
      seen.current.add(r.id)
      const to = r.to_location_id ? locations?.[r.to_location_id]?.name : null
      if (r.decision === 'DONATE') toast(`❤️ ${r.crate_id} donated to ${to}`, { duration: 5000 })
      else if (r.decision === 'DISCARD') toast.error(`🗑️ ${r.crate_id} discarded`, { duration: 5000 })
      else toast(`🔄 ${r.crate_id} rerouted to ${to}`, { duration: 5000, style: { background: '#FFF7ED', fontWeight: 600 } })
    }
    for (const a of state.new_alerts || []) {
      if (seen.current.has(a.id)) continue
      seen.current.add(a.id)
      if (['rerouted', 'donated', 'discarded'].includes(a.type)) continue
      if (a.severity === 'critical') toast.error(`${ALERT_ICONS[a.type] || ''} ${a.message}`, { duration: 4500 })
      else if (a.type === 'temp_excursion') toast(`🌡️ ${a.message}`, { duration: 3500, style: { background: '#FEF3C7' } })
    }
  }, [state, locations])
}
