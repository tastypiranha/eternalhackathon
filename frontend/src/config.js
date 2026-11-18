export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
export const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const STATUS_COLORS = {
  fresh: '#16A34A',
  watch: '#EAB308',
  at_risk: '#F97316',
  critical: '#DC2626',
  spoiled: '#6B7280',
}
export const STATUS_LABELS = {
  fresh: 'Fresh',
  watch: 'Watch',
  at_risk: 'At risk',
  critical: 'Critical',
  spoiled: 'Spoiled',
}
export const STATUS_ORDER = ['fresh', 'watch', 'at_risk', 'critical', 'spoiled']
export const TYPE_ICONS = { warehouse: '🏭', dark_store: '⚡', restaurant: '🍽️', food_bank: '❤️' }
export const TYPE_LABELS = {
  warehouse: 'Hyperpure warehouse',
  dark_store: 'Blinkit dark store',
  restaurant: 'Zomato partner restaurant',
  food_bank: 'Feeding India partner',
}
export const ALERT_ICONS = {
  temp_excursion: '🌡️',
  door_open: '🚪',
  shock: '💥',
  compressor_fail: '❄️',
  status_change: '⚠️',
  rerouted: '🔄',
  donated: '❤️',
  discarded: '🗑️',
  delivery_rejected: '❌',
}
export const SEVERITY_COLORS = { info: '#3B82F6', warning: '#F59E0B', critical: '#DC2626' }
export const DECISION_STYLE = {
  REDIRECT: { bg: 'bg-orange-50', border: 'border-orange-300', icon: '🔄', color: '#F97316' },
  DONATE: { bg: 'bg-pink-50', border: 'border-pink-300', icon: '❤️', color: '#DB2777' },
  DISCARD: { bg: 'bg-gray-100', border: 'border-gray-300', icon: '🗑️', color: '#6B7280' },
}
export const BRAND_RED = '#E23744'

export const worstStatus = (statuses) =>
  statuses.reduce((w, s) => (STATUS_ORDER.indexOf(s) > STATUS_ORDER.indexOf(w) ? s : w), 'fresh')

export const fmtTime = (iso) => (iso ? iso.slice(11, 16) : '--:--')
export const fmtH = (x) => (x == null ? '–' : `${Number(x).toFixed(1)} h`)
export const fmtT = (x) => (x == null ? '–' : `${Number(x).toFixed(1)} °C`)
export const fmtDuration = (min) => {
  const m = Math.round(min || 0)
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  const r = m % 60
  return r ? `${h} h ${r} min` : `${h} h`
}
export const areaOf = (locations, id) => locations?.[id]?.area || id || '–'
