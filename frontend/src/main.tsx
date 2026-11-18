import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import "./master.css";
import { API_BASE, initConfig } from "./demo/config";
import type { World } from "./demo/types";

const root = ReactDOM.createRoot(document.getElementById("root")!);

function Waiting({ error }: { error?: string }) {
  return (
    <div className="boot-screen">
      <div className="boot-card">
        <strong>
          Fresh<span>Sense</span>
        </strong>
        {error ? (
          <>
            <p>Can’t reach the FreshSense backend at {API_BASE}.</p>
            <code>cd backend && uvicorn main:app --port 8000</code>
            <small>{error} · retrying every 3 s…</small>
          </>
        ) : (
          <p>Connecting to the FreshSense backend…</p>
        )}
      </div>
    </div>
  );
}

async function boot() {
  root.render(<Waiting />);
  for (;;) {
    try {
      const get = (p: string) =>
        fetch(API_BASE + p).then((r) => {
          if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`);
          return r.json();
        });
      const [meta, calibration, state] = await Promise.all([
        get("/api/locations"),
        get("/api/calibration"),
        get("/api/state"),
      ]);
      initConfig(meta, calibration, state as World);
      root.render(
        <React.StrictMode>
          <App initial={state as World} />
        </React.StrictMode>,
      );
      return;
    } catch (e) {
      root.render(<Waiting error={(e as Error).message} />);
      await new Promise((r) => setTimeout(r, 3000));
    }
  }
}
boot();
