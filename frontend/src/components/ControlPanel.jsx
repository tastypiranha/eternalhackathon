import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import * as api from '../api'

const btn = 'rounded-md px-2.5 py-1.5 text-xs font-semibold shadow-sm transition active:scale-95 disabled:opacity-40'

async function run(fn, okMsg) {
  try {
    await fn()
    if (okMsg) toast.success(okMsg, { duration: 1500 })
  } catch (e) {
    toast.error(`Request failed: ${e.message}. Is the backend running on :8000?`)
  }
}

export default function ControlPanel({ state }) {
  const crates = state?.crates || []
  const trucks = state?.trucks || []
  const fefoTop = state?.dispatch?.fefo?.[0]?.crate_id
  const [crateId, setCrateId] = useState(null)
  const [truckId, setTruckId] = useState(null)
  const [heatMin, setHeatMin] = useState(120)
  // default to the most urgent crate (FEFO #1) and its truck
  useEffect(() => {
    if (!crateId && fefoTop) setCrateId(fefoTop)
  }, [crateId, fefoTop])
  useEffect(() => {
    const c = crates.find((x) => x.id === (crateId || fefoTop))
    if (!truckId && c?.truck_id) setTruckId(c.truck_id)
  }, [truckId, crateId, fefoTop, crates])
  const [tagOpen, setTagOpen] = useState(false)

  // keep selections valid when crates are delivered / respawned
  useEffect(() => {
    if (crateId && crates.length && !crates.find((c) => c.id === crateId)) {
      setCrateId(crates.find((c) => c.truck_id)?.id || crates[0].id)
    }
  }, [crates, crateId])

  const truck = trucks.find((t) => t.id === truckId)
  const paused = state?.paused

  return (
    <div className="relative flex h-full items-center gap-4 overflow-x-auto border-t bg-white px-4">
      <Group label="Crate">
        <select className="rounded border px-1.5 py-1 text-xs" value={crateId || ''} onChange={(e) => setCrateId(e.target.value)}>
          {crates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.id} {c.emoji} {c.product_label} · {c.hours_left} h {c.truck_id ? `· ${c.truck_id}` : '· cold room'}
              {c.id === fefoTop ? ' (most urgent)' : ''}
            </option>
          ))}
        </select>
        <select className="rounded border px-1.5 py-1 text-xs" value={heatMin} onChange={(e) => setHeatMin(Number(e.target.value))} title="How long the crate is left outside refrigeration (sim minutes)">
          {[30, 60, 120, 240, 480].map((m) => (
            <option key={m} value={m}>
              out {m < 60 ? `${m} min` : `${m / 60} h`}
            </option>
          ))}
        </select>
        <button className={`${btn} bg-orange-500 text-white hover:bg-orange-600`} onClick={() => run(() => api.heat(crateId, heatMin), `🔥 ${crateId} left out of the cold for ${heatMin} min`)}>
          🔥 Leave out of cold
        </button>
        <button className={`${btn} bg-amber-100 text-amber-900 hover:bg-amber-200`} onClick={() => run(() => api.shock(crateId), `💥 Shock logged on ${crateId}`)}>
          💥 Log shock
        </button>
      </Group>

      <Group label="Truck">
        <select className="rounded border px-1.5 py-1 text-xs" value={truckId || ''} onChange={(e) => setTruckId(e.target.value)}>
          {trucks.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.driver.replace(' (demo)', '')})
            </option>
          ))}
        </select>
        <button className={`${btn} bg-sky-100 text-sky-900 hover:bg-sky-200`} onClick={() => run(() => api.door(truckId), `🚪 ${truckId} door opened`)}>
          🚪 Open door
        </button>
        {truck?.compressor_ok !== false ? (
          <button className={`${btn} bg-red-600 text-white hover:bg-red-700`} onClick={() => run(() => api.compressorFail(truckId), `❄️ ${truckId} compressor failed`)}>
            ❄️ Compressor fail
          </button>
        ) : (
          <button className={`${btn} bg-green-600 text-white hover:bg-green-700`} onClick={() => run(() => api.compressorFix(truckId), `✅ ${truckId} compressor fixed`)}>
            ✅ Fix compressor
          </button>
        )}
      </Group>

      <Group label="Simulation">
        <button
          className={`${btn} ${paused ? 'pulse-green bg-green-600 text-white' : 'bg-gray-200 text-gray-800'}`}
          onClick={() => run(() => api.simControl({ paused: !paused }))}
        >
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <select
          className="rounded border px-1.5 py-1 text-xs"
          value={state?.minutes_per_tick || 1}
          onChange={(e) => run(() => api.simControl({ minutes_per_tick: Number(e.target.value) }))}
        >
          {[1, 2, 5, 10].map((m) => (
            <option key={m} value={m}>
              {m} min/tick
            </option>
          ))}
        </select>
        <button
          className={`${btn} bg-gray-800 text-white hover:bg-gray-900`}
          onClick={() => {
            if (window.confirm('Reset the demo to its starting state?')) run(() => api.resetDemo(), '🔄 Demo reset (paused)')
          }}
        >
          🔄 Reset demo
        </button>
      </Group>

      <Group label="Tag">
        <button className={`${btn} ${tagOpen ? 'bg-indigo-600 text-white' : 'bg-indigo-100 text-indigo-900'}`} onClick={() => setTagOpen((o) => !o)}>
          📡 Live tag
        </button>
      </Group>
      {tagOpen && <LiveTagSlider onClose={() => setTagOpen(false)} />}
    </div>
  )
}

function Group({ label, children }) {
  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <span className="text-[10px] font-bold uppercase tracking-wide text-gray-400">{label}</span>
      {children}
    </div>
  )
}

function LiveTagSlider({ onClose }) {
  const [v, setV] = useState({ temp_c: 3, humidity: 60, door_open: false })
  const [sending, setSending] = useState(false)
  const latest = useRef(v)
  latest.current = v

  useEffect(() => {
    if (!sending) return
    const send = () => api.tagReading({ crate_id: 'C-001', ...latest.current, source: 'slider' }).catch(() => {})
    send()
    const t = setInterval(send, 2000)
    return () => clearInterval(t)
  }, [sending])

  const row = (label, key, min, max, step, unit) => (
    <label className="block text-xs">
      <div className="flex justify-between">
        <span>{label}</span>
        <b>
          {v[key]}
          {unit}
        </b>
      </div>
      <input
        type="range"
        className="w-full"
        min={min}
        max={max}
        step={step}
        value={v[key]}
        onChange={(e) => setV({ ...v, [key]: Number(e.target.value) })}
      />
    </label>
  )

  return (
    <div className="fixed bottom-24 right-4 z-[2000] w-72 rounded-xl border bg-white p-3 shadow-2xl">
      <div className="mb-1 flex items-center justify-between">
        <b className="text-sm">📡 Live tag → C-001</b>
        <button className="text-gray-400 hover:text-gray-700" onClick={onClose}>
          ✕
        </button>
      </div>
      <p className="mb-2 text-[11px] text-gray-500">Backup for the Wokwi ESP32. Sends a tag reading every 2 s while on.</p>
      {row('Temperature', 'temp_c', -2, 35, 0.5, ' °C')}
      {row('Humidity', 'humidity', 40, 100, 1, ' %')}
      
      <label className="mt-1 flex items-center gap-2 text-xs">
        <input type="checkbox" checked={v.door_open} onChange={(e) => setV({ ...v, door_open: e.target.checked })} /> Door open
      </label>
      <button
        className={`mt-2 w-full rounded-md py-1.5 text-xs font-semibold ${sending ? 'bg-red-600 text-white' : 'bg-indigo-600 text-white'}`}
        onClick={() => setSending((s) => !s)}
      >
        {sending ? '■ Stop sending' : '▶ Send as live tag'}
      </button>
    </div>
  )
}
