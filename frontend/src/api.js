import { API_BASE } from './config'

const post = (path, body) =>
  fetch(API_BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

const get = (path) =>
  fetch(API_BASE + path).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  })

export const heat = (id) => post(`/api/simulate/heat/${id}`)
export const shock = (id) => post(`/api/simulate/shock/${id}`)
export const door = (tid) => post(`/api/simulate/door/${tid}`)
export const compressorFail = (tid) => post(`/api/simulate/compressor/${tid}/fail`)
export const compressorFix = (tid) => post(`/api/simulate/compressor/${tid}/fix`)
export const simControl = (body) => post('/api/sim/control', body)
export const resetDemo = () => post('/api/demo/reset')
export const tagReading = (body) => post('/api/tag/reading', body)
export const getJourney = (id) => get(`/api/crates/${id}/journey`)
export const getAnalytics = () => get('/api/analytics')
export const getLocations = () => get('/api/locations')
export const getState = () => get('/api/state')
