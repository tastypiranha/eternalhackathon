import { STATUS_COLORS, STATUS_LABELS } from '../config'

export function StatusBadge({ status, className = '' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold text-white ${className}`}
      style={{ background: STATUS_COLORS[status] }}
    >
      {STATUS_LABELS[status] || status}
    </span>
  )
}

export function FreshnessRing({ score, status, size = 56, stroke = 6 }) {
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, score || 0)) / 100
  return (
    <svg width={size} height={size} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} stroke="#E5E7EB" strokeWidth={stroke} fill="none" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke={STATUS_COLORS[status]}
        strokeWidth={stroke}
        fill="none"
        strokeDasharray={circ}
        strokeDashoffset={circ * (1 - pct)}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.8s ease, stroke 0.5s' }}
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fontSize={size * 0.28} fontWeight="700" fill="#111827">
        {Math.round(score ?? 0)}
      </text>
    </svg>
  )
}
