import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getJourney } from '../api'
import { STATUS_COLORS, areaOf, fmtDuration, fmtH, fmtT, fmtTime } from '../config'
import { FreshnessRing, StatusBadge } from './common'

const toMs = (ts) => new Date(ts).getTime()
const tick = (ms) => {
  const d = new Date(ms)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
const dayTick = (ms) => {
  const d = new Date(ms)
  return `${d.getDate()}/${d.getMonth() + 1} ${tick(ms)}`
}

export default function JourneyDrawer({ crateId, locations, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!crateId) return
    let alive = true
    setData(null)
    setError(null)
    const load = () =>
      getJourney(crateId)
        .then((j) => alive && (setData(j), setError(null)))
        .catch((e) => alive && setError(e.message))
    load()
    const t = setInterval(load, 5000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [crateId])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!crateId) return null
  return (
    <div className="fixed inset-0 z-[3000] flex justify-end bg-black/20" onClick={onClose}>
      <div className="drawer-enter h-full w-[680px] max-w-full overflow-y-auto bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {!data && !error && <div className="p-6 text-sm text-gray-500">Loading journey for {crateId}…</div>}
        {error && !data && (
          <div className="p-6 text-sm text-red-600">
            Could not load journey ({error}).{' '}
            <button className="underline" onClick={onClose}>
              Close
            </button>
          </div>
        )}
        {data && <Report j={data} locations={locations} onClose={onClose} />}
      </div>
    </div>
  )
}

function Report({ j, locations, onClose }) {
  const { crate: c, product: p, summary: s } = j
  const [range, setRange] = useState('full')
  const all = useMemo(() => j.readings.map((r) => ({ ...r, t: toMs(r.ts) })), [j.readings])
  const tripReadings = useMemo(() => all.filter((r) => r.stage === 'in_transit'), [all])
  const hasTrip = tripReadings.length >= 3
  const readings = range === 'trip' && hasTrip ? tripReadings : all
  const blamed = j.blame.stage
  const blamedIdx = useMemo(() => {
    let best = -1
    let max = -1
    j.stages.forEach((st, i) => {
      if (st.stage === blamed && st.extra_loss_h > max) {
        max = st.extra_loss_h
        best = i
      }
    })
    return best
  }, [j.stages, blamed])
  const domain = readings.length ? [readings[0].t, readings[readings.length - 1].t] : ['auto', 'auto']
  const multiDay = readings.length && readings[readings.length - 1].t - readings[0].t > 20 * 3600 * 1000
  const xAxis = (
    <XAxis
      dataKey="t"
      type="number"
      domain={domain}
      scale="time"
      tickFormatter={multiDay ? dayTick : tick}
      tick={{ fontSize: 10 }}
      minTickGap={40}
    />
  )
  const tooltip = <Tooltip labelFormatter={(ms) => dayTick(ms)} contentStyle={{ fontSize: 11 }} />
  const excAreas = j.excursions
    .filter((e) => range === 'full' || !hasTrip || toMs(e.end) >= readings[0].t)
    .map((e, i) => (
    <ReferenceArea key={i} x1={toMs(e.start)} x2={Math.max(toMs(e.end), toMs(e.start) + 60000)} fill="#DC2626" fillOpacity={0.12} />
  ))

  return (
    <div>
      {/* header */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b bg-white px-5 py-3">
        <span className="text-2xl">{c.emoji}</span>
        <div>
          <div className="text-lg font-bold">
            {c.id} · {p.label} · {c.weight_kg} kg
          </div>
          <div className="text-xs text-gray-500">
            {c.delivered ? `Delivered to ${locations?.[c.delivered_to]?.name || c.delivered_to}` : c.discarded ? 'Discarded' : c.truck_id ? `On ${c.truck_id}, ${c.stage.replace('_', ' ')}` : 'In cold room (live tag)'}
          </div>
        </div>
        <StatusBadge status={s.status} className="ml-2" />
        <button className="ml-auto rounded px-2 py-1 text-xl text-gray-400 hover:bg-gray-100 hover:text-gray-700" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="space-y-4 p-5">
        {/* summary */}
        <div className="flex items-center gap-4 rounded-xl bg-gray-50 p-3">
          <FreshnessRing score={s.freshness_score} status={s.status} size={72} stroke={7} />
          <Kpi label="Hours left" value={fmtH(s.hours_left)} big color={STATUS_COLORS[s.status]} />
          <Kpi label="If it stays at current temp" value={fmtH(c.hours_left_if_unchanged)} />
          <Kpi label="Temp / humidity" value={`${fmtT(c.temp_c)} · ${c.humidity}%`} />
          <Kpi label="VOC index" value={c.voc_index} />
        </div>
        {(c.destination_id || c.original_destination_id) && (
          <div className="rounded-lg border p-2.5 text-xs">
            {c.redirected ? (
              <>
                <div className="font-semibold">
                  🔄 Original: {areaOf(locations, c.original_destination_id)} → Now: {locations?.[c.destination_id]?.name}
                </div>
                <div className="mt-0.5 text-gray-600">{c.redirect_reason}</div>
              </>
            ) : (
              <div>
                Destination: <b>{locations?.[c.destination_id]?.name}</b>
                {c.eta_min != null && ` · ETA ${c.eta_min} min`}
              </div>
            )}
          </div>
        )}

        {/* blame */}
        <div className={`rounded-lg p-2.5 text-sm font-medium ${j.blame.share_pct ? 'bg-red-50 text-red-800' : 'bg-green-50 text-green-800'}`}>
          🔎 {j.blame.text}
        </div>

        {/* range toggle */}
        <div className="flex items-center gap-1 text-xs">
          <span className="mr-1 text-gray-500">Charts show:</span>
          {[
            ['full', 'Full journey'],
            ['trip', 'This trip (live)'],
          ].map(([k, l]) => (
            <button
              key={k}
              disabled={k === 'trip' && !hasTrip}
              onClick={() => setRange(k)}
              className={`rounded-full border px-2.5 py-0.5 font-semibold disabled:opacity-40 ${range === k ? 'border-gray-900 bg-gray-900 text-white' : 'bg-white'}`}
            >
              {l}
            </button>
          ))}
        </div>

        {/* temperature */}
        <Chart title="Temperature (°C)" hint={`green band = safe (≤ ${p.max_safe_c} °C), red = excursion`}>
          <ResponsiveContainer width="100%" height={210}>
            <ComposedChart data={readings} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              {xAxis}
              <YAxis tick={{ fontSize: 10 }} domain={[(min) => Math.min(-1, Math.floor(min)), (max) => Math.max(p.max_safe_c + 3, Math.ceil(max + 1))]} />
              {tooltip}
              <ReferenceArea y1={-5} y2={p.max_safe_c} fill="#16A34A" fillOpacity={0.08} />
              {excAreas}
              <ReferenceLine y={p.max_safe_c} stroke="#DC2626" strokeDasharray="5 4" label={{ value: 'safe limit', fontSize: 10, fill: '#DC2626', position: 'insideTopRight' }} />
              <Line type="monotone" dataKey="temp_c" name="Temp °C" stroke="#2563EB" dot={false} strokeWidth={2} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Chart>

        {/* humidity */}
        <Chart title="Humidity (%)">
          <ResponsiveContainer width="100%" height={120}>
            <ComposedChart data={readings} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              {xAxis}
              <YAxis tick={{ fontSize: 10 }} domain={[40, 100]} />
              {tooltip}
              <Line type="monotone" dataKey="humidity" name="Humidity %" stroke="#0D9488" dot={false} strokeWidth={2} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Chart>

        {/* freshness */}
        <Chart title="Freshness score" hint="drops faster whenever it gets warm">
          <ResponsiveContainer width="100%" height={150}>
            <ComposedChart data={readings} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              {xAxis}
              <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
              {tooltip}
              <ReferenceLine y={70} stroke={STATUS_COLORS.watch} strokeDasharray="3 3" />
              <ReferenceLine y={40} stroke={STATUS_COLORS.at_risk} strokeDasharray="3 3" />
              <ReferenceLine y={15} stroke={STATUS_COLORS.critical} strokeDasharray="3 3" />
              <Area type="monotone" dataKey="freshness_score" name="Freshness" stroke="#E23744" fill="#E23744" fillOpacity={0.12} strokeWidth={2} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Chart>

        {/* stage table */}
        <div>
          <h4 className="mb-1 text-sm font-bold">Journey stages</h4>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-[11px]">
              <thead className="bg-gray-50 text-left text-gray-500">
                <tr>
                  <th className="px-2 py-1">Stage</th>
                  <th className="px-2 py-1">Where</th>
                  <th className="px-2 py-1">Time</th>
                  <th className="px-2 py-1 text-right">Avg °C</th>
                  <th className="px-2 py-1 text-right">Max °C</th>
                  <th className="px-2 py-1 text-right">Avg RH</th>
                  <th className="px-2 py-1 text-right">Min above limit</th>
                  <th className="px-2 py-1 text-right">Life used</th>
                  <th className="px-2 py-1 text-right">Extra loss</th>
                </tr>
              </thead>
              <tbody>
                {j.stages.map((st, i) => (
                  <tr key={i} className={`border-t ${i === blamedIdx ? 'bg-red-50 font-semibold' : ''}`}>
                    <td className="px-2 py-1 whitespace-nowrap">{st.label}</td>
                    <td className="px-2 py-1">{st.location_name}</td>
                    <td className="px-2 py-1 whitespace-nowrap">
                      {fmtTime(st.start)}–{fmtTime(st.end)}
                      <div className="text-gray-400">{fmtDuration(st.duration_min)}</div>
                    </td>
                    <td className="px-2 py-1 text-right">{st.avg_temp_c}</td>
                    <td className={`px-2 py-1 text-right ${st.max_temp_c > p.max_safe_c ? 'text-red-600' : ''}`}>{st.max_temp_c}</td>
                    <td className="px-2 py-1 text-right">{st.avg_humidity}%</td>
                    <td className={`px-2 py-1 text-right ${st.minutes_above_limit ? 'text-red-600' : ''}`}>{st.minutes_above_limit}</td>
                    <td className="px-2 py-1 text-right">{st.life_used_h} h</td>
                    <td className={`px-2 py-1 text-right ${st.extra_loss_h > 1 ? 'text-red-600' : ''}`}>{st.extra_loss_h} h</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* excursions */}
        {j.excursions.length > 0 && (
          <div>
            <h4 className="mb-1 text-sm font-bold">Temperature excursions</h4>
            <ul className="space-y-0.5 text-xs">
              {j.excursions.map((e, i) => (
                <li key={i}>
                  🔥 {fmtDuration(e.minutes)} at up to {e.peak_temp_c} °C · {e.stage.replace('_', ' ')} · {dayTick(toMs(e.start))}–{tick(toMs(e.end))}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="border-t pt-2 text-[11px] text-gray-500">
          Picked up {dayTick(toMs(s.picked_up_at))} · Total life {s.total_life_h} h at {p.t_ref_c} °C · Used {s.life_used_h} h · Extra loss
          from heat {s.extra_loss_h} h
        </div>
      </div>
    </div>
  )
}

function Kpi({ label, value, big, color }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-wide text-gray-400">{label}</div>
      <div className={`${big ? 'text-2xl' : 'text-sm'} font-bold`} style={color ? { color } : undefined}>
        {value}
      </div>
    </div>
  )
}

function Chart({ title, hint, children }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline gap-2">
        <h4 className="text-sm font-bold">{title}</h4>
        {hint && <span className="text-[11px] text-gray-400">{hint}</span>}
      </div>
      {children}
    </div>
  )
}
