import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import {
  DECISION_STYLE,
  STATUS_COLORS,
  STATUS_LABELS,
  TYPE_ICONS,
  TYPE_LABELS,
  areaOf,
  fmtH,
  fmtT,
  worstStatus,
} from '../config'

const CENTER = [12.97, 77.64]

function ZoomClass() {
  const map = useMap()
  useMapEvents({
    zoomstart: () => map.getContainer().classList.add('zooming'),
    zoomend: () => map.getContainer().classList.remove('zooming'),
  })
  return null
}

function InvalidateOnShow({ visible }) {
  const map = useMap()
  useEffect(() => {
    if (visible) setTimeout(() => map.invalidateSize(), 50)
  }, [visible, map])
  return null
}

function FlyToRedirect({ target, follow }) {
  const map = useMap()
  useEffect(() => {
    if (!follow || !target) return
    map.flyTo(target.point, 12, { duration: 1.5 })
    const back = setTimeout(() => map.flyTo(CENTER, 11, { duration: 1.5 }), 6000)
    return () => clearTimeout(back)
  }, [target, follow, map])
  return null
}

function LocationMarker({ loc }) {
  const icon = useMemo(
    () =>
      L.divIcon({
        className: '',
        html: `<div class="loc-icon loc-${loc.type}">${TYPE_ICONS[loc.type]}</div>`,
        iconSize: loc.type === 'warehouse' ? [36, 36] : [30, 30],
        iconAnchor: loc.type === 'warehouse' ? [18, 18] : [15, 15],
      }),
    [loc.type],
  )
  const d = loc.demand_kg_per_day || {}
  return (
    <Marker position={[loc.lat, loc.lng]} icon={icon}>
      <Popup>
        <div className="font-semibold">{loc.name}</div>
        <div className="text-gray-500">{TYPE_LABELS[loc.type]}</div>
        {loc.min_hours_needed != null && (
          <div className="mt-1">Accepts crates with ≥ {loc.min_hours_needed} h left on arrival</div>
        )}
        {loc.type !== 'warehouse' && (
          <div className="mt-1">
            Demand/day: 🍗 {d.chicken} kg · 🥛 {d.dairy} kg · 🥬 {d.greens} kg
          </div>
        )}
        {loc.has_cold_room && <div>❄️ Cold room</div>}
      </Popup>
    </Marker>
  )
}

function CrateLine({ c, locations, onOpen }) {
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLORS[c.status] }} />
      <span>
        {c.emoji} <b>{c.id}</b> · {fmtH(c.hours_left)} · {fmtT(c.temp_c)} → {areaOf(locations, c.destination_id)}
        {c.redirected && ' 🔄'}
      </span>
      <button className="ml-auto rounded bg-gray-900 px-1.5 py-0.5 text-[10px] font-semibold text-white" onClick={() => onOpen(c.id)}>
        Journey
      </button>
    </div>
  )
}

function TruckMarker({ truck, crates, locations, onOpen }) {
  const mine = crates.filter((c) => c.truck_id === truck.id)
  const worst = worstStatus(mine.map((c) => c.status))
  const alarm = !truck.compressor_ok || truck.door_open
  const icon = useMemo(
    () =>
      L.divIcon({
        className: 'truck-icon',
        html: `<div class="truck-wrap ${alarm ? 'truck-alarm' : ''}"><div class="truck-icon-inner" style="border-color:${STATUS_COLORS[worst]}">🚚</div><div class="truck-label" style="background:${truck.color}">${truck.name}</div></div>`,
        iconSize: [60, 54],
        iconAnchor: [30, 18],
      }),
    [worst, alarm, truck.name, truck.color],
  )
  return (
    <Marker position={[truck.lat, truck.lng]} icon={icon} zIndexOffset={1000}>
      <Tooltip direction="top" offset={[0, -18]}>
        {truck.name} · {truck.driver} · {truck.compressor_ok ? '❄️ OK' : '⚠️ COMPRESSOR FAILED'}
        {truck.door_open ? ' · 🚪 door open' : ''}
      </Tooltip>
      <Popup minWidth={280}>
        <div className="mb-1 font-semibold">
          {truck.name} — {truck.driver}
        </div>
        <div className="mb-1 text-gray-500">
          {truck.status === 'at_warehouse' ? 'At warehouse, loading next trip' : `Next stop: ${areaOf(locations, truck.stops[0]?.location_id)} (${truck.stops[0]?.eta_min ?? '–'} min)`}
        </div>
        {mine.length === 0 && <div className="text-gray-400">No crates on board</div>}
        {mine.map((c) => (
          <CrateLine key={c.id} c={c} locations={locations} onOpen={onOpen} />
        ))}
      </Popup>
    </Marker>
  )
}

function TagMarker({ crate, onOpen }) {
  const icon = useMemo(
    () =>
      L.divIcon({
        className: '',
        html: `<div class="tag-icon" style="border-color:${STATUS_COLORS[crate.status]}">${crate.emoji} ${crate.id} 📡 LIVE TAG</div>`,
        iconSize: [130, 24],
        iconAnchor: [-14, 30],
      }),
    [crate.status, crate.emoji, crate.id],
  )
  return (
    <Marker position={[crate.lat, crate.lng]} icon={icon} eventHandlers={{ click: () => onOpen(crate.id) }}>
      <Tooltip direction="right">
        Cold-room crate with the live Wokwi tag · {fmtT(crate.temp_c)} · {fmtH(crate.hours_left)} left · click for journey
      </Tooltip>
    </Marker>
  )
}

export default function MapView({ state, locations, onOpenCrate, visible = true }) {
  const [recent, setRecent] = useState([])
  const [follow, setFollow] = useState(true)
  const [flyTarget, setFlyTarget] = useState(null)
  const seen = useRef(new Set())

  // Collect new redirects for the animation (deduped by id)
  useEffect(() => {
    if (!state || !locations) return
    const fresh = (state.new_redirects || []).filter((r) => !seen.current.has(r.id) && r.to_location_id)
    if (!fresh.length) return
    fresh.forEach((r) => seen.current.add(r.id))
    const items = fresh.map((r) => {
      const from = locations[r.from_location_id]
      const to = locations[r.to_location_id]
      return {
        id: r.id,
        decision: r.decision,
        from_point: r.from_point,
        oldDest: from ? [from.lat, from.lng] : null,
        newDest: [to.lat, to.lng],
        expiresAt: Date.now() + 20000,
      }
    })
    setRecent((prev) => [...prev, ...items])
    const last = items[items.length - 1]
    setFlyTarget({ id: last.id, point: last.newDest })
  }, [state, locations])

  // Mark redirects already in the initial state as seen (no animation on page load)
  const initialised = useRef(false)
  useEffect(() => {
    if (initialised.current || !state) return
    initialised.current = true
    ;(state.redirects || []).forEach((r) => seen.current.add(r.id))
  }, [state])

  useEffect(() => {
    const t = setInterval(() => setRecent((prev) => prev.filter((r) => r.expiresAt > Date.now())), 1000)
    return () => clearInterval(t)
  }, [])

  const crates = state?.crates || []
  const trucks = state?.trucks || []
  const tagCrates = crates.filter((c) => !c.truck_id)
  const locList = locations ? Object.values(locations) : []

  return (
    <div className="relative h-full w-full">
      <MapContainer center={CENTER} zoom={11} className="h-full w-full" zoomControl preferCanvas={false}>
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap contributors'
          maxZoom={19}
          className="osm-tiles"
        />
        <ZoomClass />
        <InvalidateOnShow visible={visible} />
        <FlyToRedirect target={flyTarget} follow={follow} />

        {trucks.map((t) =>
          t.route_points?.length > 1 ? (
            <Polyline key={`route-${t.id}`} positions={t.route_points} pathOptions={{ color: t.color, weight: 4, opacity: 0.75 }} />
          ) : null,
        )}

        {recent.map((r) => (
          <FragmentRedirect key={r.id} r={r} />
        ))}

        {locList.map((loc) => (
          <LocationMarker key={loc.id} loc={loc} />
        ))}
        {tagCrates.map((c) => (
          <TagMarker key={c.id} crate={c} onOpen={onOpenCrate} />
        ))}
        {trucks.map((t) => (
          <TruckMarker key={t.id} truck={t} crates={crates} locations={locations} onOpen={onOpenCrate} />
        ))}
      </MapContainer>

      <Legend follow={follow} setFollow={setFollow} />
      <ImpactOverlay impact={state?.impact} />
    </div>
  )
}

function FragmentRedirect({ r }) {
  const color = DECISION_STYLE[r.decision]?.color || '#F97316'
  return (
    <>
      {r.oldDest && (
        <Polyline positions={[r.from_point, r.oldDest]} pathOptions={{ color: '#9CA3AF', dashArray: '8 8', weight: 3 }} />
      )}
      <Polyline positions={[r.from_point, r.newDest]} pathOptions={{ color, weight: 7, opacity: 0.9, className: 'route-glow' }} />
      <CircleMarker center={r.newDest} radius={18} pathOptions={{ color, weight: 3, fill: false, className: 'pulse-ring' }} />
    </>
  )
}

function Legend({ follow, setFollow }) {
  return (
    <div className="absolute bottom-3 left-3 z-[1000] rounded-lg bg-white/95 p-2.5 text-[11px] shadow-md">
      <div className="mb-1 font-semibold">Eternal network (demo)</div>
      {Object.entries(TYPE_LABELS).map(([k, v]) => (
        <div key={k}>
          {TYPE_ICONS[k]} {v}
        </div>
      ))}
      <div className="mt-1.5 flex flex-wrap gap-x-2 gap-y-0.5">
        {Object.entries(STATUS_LABELS).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLORS[k] }} />
            {v}
          </span>
        ))}
      </div>
      <label className="mt-1.5 flex cursor-pointer items-center gap-1">
        <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> Follow redirects
      </label>
    </div>
  )
}

function ImpactOverlay({ impact }) {
  if (!impact) return null
  return (
    <div className="absolute right-3 top-3 z-[1000] rounded-lg bg-white/95 px-3 py-2 text-[11px] shadow-md">
      <div className="font-semibold text-gray-500">TODAY (demo)</div>
      <div className="mt-0.5 flex gap-3">
        <div>
          <div className="text-lg font-bold text-orange-600">{impact.crates_redirected}</div>redirected
        </div>
        <div>
          <div className="text-lg font-bold text-pink-600">{impact.crates_donated}</div>donated
        </div>
        <div>
          <div className="text-lg font-bold text-green-600">{impact.kg_saved}</div>kg saved
        </div>
        <div>
          <div className="text-lg font-bold text-red-600">{impact.kg_wasted}</div>kg wasted
        </div>
      </div>
    </div>
  )
}
