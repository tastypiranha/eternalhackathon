import { useEffect, useRef, useState } from 'react'
import { getLocations, getState } from '../api'
import { USE_MOCK, WS_URL } from '../config'
import mockState from '../mock/state.json'
import mockLocations from '../mock/locations.json'

/**
 * Live State from the backend.
 * WebSocket first; after 3 failed attempts also polls GET /api/state every 2 s
 * while retrying the socket every 10 s.
 * connection: 'live' | 'polling' | 'offline' | 'mock'
 */
export default function useLiveState() {
  const [state, setState] = useState(USE_MOCK ? mockState : null)
  const [connection, setConnection] = useState(USE_MOCK ? 'mock' : 'offline')
  const [meta, setMeta] = useState(USE_MOCK ? mockLocations : null)
  const refs = useRef({ ws: null, failures: 0, poll: null, retry: null, closed: false })

  useEffect(() => {
    getLocations()
      .then(setMeta)
      .catch(() => setMeta(mockLocations))
  }, [])

  useEffect(() => {
    if (USE_MOCK) return
    const r = refs.current
    r.closed = false

    const startPolling = () => {
      if (r.poll) return
      setConnection('polling')
      const tick = () =>
        getState()
          .then((s) => setState(s))
          .catch(() => setConnection('offline'))
      tick()
      r.poll = setInterval(tick, 2000)
    }
    const stopPolling = () => {
      if (r.poll) clearInterval(r.poll)
      r.poll = null
    }

    const connect = () => {
      if (r.closed) return
      let ws
      try {
        ws = new WebSocket(WS_URL)
      } catch {
        scheduleRetry()
        return
      }
      r.ws = ws
      ws.onopen = () => {
        r.failures = 0
        stopPolling()
        setConnection('live')
      }
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data)
          if (data.type === 'state') setState(data)
        } catch {
          /* ignore malformed frames */
        }
      }
      ws.onclose = () => {
        if (r.ws === ws) r.ws = null
        if (r.closed) return
        r.failures += 1
        if (r.failures >= 3) startPolling()
        else setConnection('offline')
        scheduleRetry()
      }
      ws.onerror = () => ws.close()
    }

    const scheduleRetry = () => {
      if (r.closed) return
      const delay = r.failures >= 3 ? 10000 : Math.min(4000, 1000 * 2 ** Math.max(0, r.failures - 1))
      clearTimeout(r.retry)
      r.retry = setTimeout(connect, delay)
    }

    connect()
    return () => {
      r.closed = true
      clearTimeout(r.retry)
      stopPolling()
      if (r.ws) r.ws.close()
    }
  }, [])

  return { state, connection, meta }
}
