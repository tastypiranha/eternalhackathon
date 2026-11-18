import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { API_BASE, WS_URL, setDemoTargets } from "../demo/config";
import type { DemoAction, World } from "../demo/types";

const post = (path: string, body?: unknown) =>
  fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });

export type Connection = "live" | "polling" | "offline";

/**
 * Live world from the FreshSense backend: WebSocket push every tick, polling fallback after 3 failures.
 * `act` sends the dashboard's actions to the backend API.
 */
export function useDemo(initial: World) {
  const [world, setWorld] = useState<World>(initial);
  const [connection, setConnection] = useState<Connection>("live");
  const seen = useRef(new Set<string>([...initial.alerts.map((a) => a.id)]));

  useEffect(() => {
    let ws: WebSocket | null = null,
      failures = 0,
      closed = false,
      retry: ReturnType<typeof setTimeout> | undefined,
      poll: ReturnType<typeof setInterval> | undefined;
    const startPolling = () => {
      if (poll) return;
      setConnection("polling");
      const tick = () =>
        fetch(API_BASE + "/api/state")
          .then((r) => r.json())
          .then(setWorld)
          .catch(() => setConnection("offline"));
      tick();
      poll = setInterval(tick, 2000);
    };
    const connect = () => {
      if (closed) return;
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        failures = 0;
        if (poll) clearInterval(poll);
        poll = undefined;
        setConnection("live");
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "state") setWorld(data);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        if (closed) return;
        failures += 1;
        if (failures >= 3) startPolling();
        else setConnection("offline");
        retry = setTimeout(connect, failures >= 3 ? 10000 : 1000 * failures);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      if (poll) clearInterval(poll);
      ws?.close();
    };
  }, []);

  useEffect(() => {
    for (const alert of world.new_alerts) {
      if (seen.current.has(alert.id)) continue;
      seen.current.add(alert.id);
      toast(alert.message, { id: alert.id, className: `demo-toast severity-${alert.severity}` });
    }
  }, [world]);

  const act = (action: DemoAction) => {
    const send = (): Promise<unknown> => {
      switch (action.type) {
        case "control":
          return post("/api/sim/control", { paused: action.paused, minutes_per_tick: action.minutes_per_tick });
        case "reset":
          return post("/api/demo/reset");
        case "heat":
          return post(`/api/simulate/heat/${action.id}?minutes=${action.minutes ?? 120}`);
        case "shock":
          return post(`/api/simulate/shock/${action.id}`);
        case "door":
          return post(`/api/simulate/door/${action.id}`);
        case "fail":
          return post(`/api/simulate/compressor/${action.id}/fail`);
        case "fix":
          return post(`/api/simulate/compressor/${action.id}/fix`);
        case "tag":
          return post("/api/tag/reading", { crate_id: "C-001", ...action.reading, source: "slider" });
      }
    };
    send()
      .then(() => {
        if (action.type === "reset") {
          toast.remove();
          seen.current.clear();
          toast("Demo reset. Ready when you are.", { id: "demo-reset", className: "demo-toast" });
          fetch(API_BASE + "/api/state")
            .then((r) => r.json())
            .then((s: World) => {
              setDemoTargets(s);
              setWorld(s);
            });
        }
      })
      .catch((e) => toast(`Backend request failed (${e.message}). Is it running on ${API_BASE}?`, { className: "demo-toast severity-critical" }));
  };
  return { world, act, connection };
}
