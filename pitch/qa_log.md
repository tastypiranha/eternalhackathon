# QA checklist (run at H6:30 and before every rehearsal)

Mark each line ✅ or ❌. For a ❌, write what happened and the steps to reproduce, then send it to A (backend) or B (frontend).

| # | Check | Run 1 | Run 2 | Run 3 |
|---|---|---|---|---|
| 1 | Backend starts; `http://localhost:8000/api/health` shows `"ok": true` | | | |
| 2 | Dashboard loads at `:5173`; connection dot is green ("Live") | | | |
| 3 | 22 locations on the map; 3 trucks with coloured routes; C-001 LIVE TAG near Hoskote | | | |
| 4 | Reset → "Paused" badge → Resume → trucks move | | | |
| 5 | Heat C-003 → 🌡️ toast in ~2 s → 🔄 reroute toast in ~7 s → grey dashed old line + glowing new line | | | |
| 6 | FIFO table shows a red ❌ row; FEFO shows C-003 at the top | | | |
| 7 | Shock C-007 → 💥 alert | | | |
| 8 | Open door on Truck 1 → 🚪 alert; Truck 1 temperatures rise | | | |
| 9 | Compressor fail on Truck 3 → C-008 rerouted, then ❤️ donated → Fix compressor works | | | |
| 10 | Click a crate → journey drawer with charts; "This trip" toggle works; Esc closes it | | | |
| 11 | Wokwi: raise DHT22 → C-001 changes within ~2 s (or the 📡 Live tag slider works) | | | |
| 12 | Pause/Resume and the speed selector work | | | |
| 13 | Reset twice in a row → identical starting picture | | | |
| 14 | Analytics tab: truck chart, benchmark, Model 1 card with 3 images | | | |
| 15 | Crates tab: cards, status filters | | | |
