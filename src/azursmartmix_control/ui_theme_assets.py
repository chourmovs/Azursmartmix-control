from __future__ import annotations


AZURA_CSS = r"""
:root{
  --az-blue: #1e88e5;
  --az-blue-dark: #1565c0;
  --az-bg: #1f242d;
  --az-card: #262c37;
  --az-card2: #2b3340;
  --az-border: rgba(255,255,255,.08);
  --az-text: rgba(255,255,255,.92);
  --az-muted: rgba(255,255,255,.65);
  --az-green: #22c55e;
  --az-red: #ef4444;
  --az-orange: #f59e0b;
  --az-cyan: #22d3ee;
  --az-violet: #a78bfa;
  --az-shadow: 0 10px 30px rgba(0,0,0,.25);
  --az-radius: 10px;
  --az-font: Inter, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial, sans-serif;
  --az-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  --grid-gap: 18px;
}

*, *::before, *::after { box-sizing: border-box; }

/* +1 point globally */
html { font-size: 17px !important; }
body { font-size: 17px !important; }

html, body { background: var(--az-bg) !important; color: var(--az-text) !important; font-family: var(--az-font) !important; }
.q-page-container, .q-layout, .q-page { background: var(--az-bg) !important; }
.q-card, .q-table__container, .q-menu, .q-dialog__inner, .q-drawer { background: transparent !important; }

.q-tab-panels,
.q-tab-panel,
.q-panel,
.q-panel-parent,
.q-tabs,
.q-tabs__content,
.q-tab-panels .q-panel,
.q-tab-panels .q-panel-parent {
  background: transparent !important;
}

.q-html,
.q-html * {
  background: transparent !important;
}

/* Force Quasar inputs to be dark */
.q-field__native,
.q-field__input,
.q-field__prefix,
.q-field__suffix,
.q-field__label,
.q-field__bottom,
.q-field__messages,
.q-placeholder,
.q-field__native::placeholder,
.q-field__input::placeholder {
  color: rgba(255,255,255,.92) !important;
}

.q-field--outlined .q-field__control:before,
.q-field--outlined .q-field__control:after {
  border-color: rgba(255,255,255,.20) !important;
}

.q-field--outlined .q-field__control,
.q-field__control {
  background: rgba(0,0,0,.18) !important;
}

.q-field__marginal,
.q-select__dropdown-icon,
.q-icon {
  color: rgba(255,255,255,.78) !important;
}

.q-menu,
.q-list,
.q-item,
.q-item__label {
  background: #151a22 !important;
  color: rgba(255,255,255,.92) !important;
}

.az-topbar{
  background: linear-gradient(0deg, var(--az-blue) 0%, var(--az-blue-dark) 100%) !important;
  color: white !important;
  border-bottom: 1px solid rgba(255,255,255,.15);
  box-shadow: var(--az-shadow);
}
.az-topbar .az-brand { font-weight: 900; }
.az-topbar .az-sub { opacity: .85; font-weight: 600; }

/* center + 90% width */
.az-wrap{
  width: 90%;
  max-width: 90%;
  margin: 0 auto;
  padding: 18px 18px 28px 18px;
}

.az-grid{ display:grid; grid-template-columns: 1fr 1fr; gap: var(--grid-gap); }
@media (max-width: 1200px){ .az-grid{ grid-template-columns: 1fr; } }

.az-card{
  background: var(--az-card) !important;
  border: 1px solid var(--az-border);
  border-radius: var(--az-radius);
  box-shadow: var(--az-shadow);
  overflow: hidden;
  min-width: 520px;
}
@media (max-width: 1200px){ .az-card{ min-width: unset; } }

.az-card-h{
  background: var(--az-blue) !important;
  color: white !important;
  padding: 12px 14px;
  font-weight: 900;
  display:flex; align-items:center; justify-content:space-between;
}
.az-card-b{ padding: 14px; background: linear-gradient(180deg, var(--az-card2), var(--az-card)); }

.az-badge{
  display:inline-flex; align-items:center; gap:8px;
  padding:6px 10px; border-radius:999px;
  font-weight:900; font-size:13px;
  border:1px solid var(--az-border);
  background: rgba(255,255,255,.05);
}
.az-dot{ width:10px; height:10px; border-radius:999px; display:inline-block; }
.az-dot.ok{ background: var(--az-green); }
.az-dot.err{ background: var(--az-red); }
.az-dot.warn{ background: var(--az-orange); }

.az-opbtn .q-btn{
  border-radius: 10px !important;
  font-weight: 950 !important;
  text-transform:none !important;
  padding: 6px 10px !important;
}
.az-opbtn .q-btn--outline{ border:1px solid rgba(255,255,255,.55) !important; color:white !important; }

.az-list{ display:flex; flex-direction:column; gap:8px; }
.az-item{
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--az-border);
  background: rgba(255,255,255,.04);
}
.az-item .idx{
  display:inline-block;
  min-width:24px;
  font-weight:950;
  color: rgba(255,255,255,.75);
}
.az-item .txt{ font-weight:650; }

.az-up-item{
  display:flex;
  flex-direction:column;
  gap: 6px;
}
.az-up-head{
  display:flex;
  align-items:flex-start;
  gap: 10px;
}
.az-up-idx{
  min-width: 28px;
  font-weight: 950;
  color: rgba(255,255,255,.76);
  line-height: 1.4;
}
.az-up-main{
  flex: 1 1 auto;
  min-width: 0;
}
.az-up-title{
  font-weight: 850;
  color: rgba(255,255,255,.96);
  word-break: break-word;
  line-height: 1.35;
}
.az-up-meta{
  display:flex;
  flex-wrap:wrap;
  gap: 8px;
  align-items:center;
  margin-top: 2px;
  font-family: var(--az-mono);
  font-size: 13px;
  color: rgba(255,255,255,.78);
}
.az-up-badge{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:4px 8px;
  border-radius:999px;
  border:1px solid rgba(255,255,255,.10);
  background: rgba(255,255,255,.05);
  font-size:12px;
  font-weight:900;
  letter-spacing:.02em;
}
.az-up-badge.runtime{
  color: rgba(34, 211, 238, .98);
  border-color: rgba(34, 211, 238, .28);
  background: rgba(34, 211, 238, .08);
}
.az-up-badge.tempo{
  color: rgba(245, 158, 11, .98);
  border-color: rgba(245, 158, 11, .30);
  background: rgba(245, 158, 11, .08);
}
.az-up-chip{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:4px 8px;
  border-radius:999px;
  border:1px solid rgba(255,255,255,.10);
  background: rgba(255,255,255,.04);
  font-size:12px;
  font-weight:850;
  line-height:1;
}
.az-up-chip.playlist{
  color: rgba(34, 211, 238, .98);
  border-color: rgba(34, 211, 238, .26);
  background: rgba(34, 211, 238, .07);
}
.az-up-chip.bpm{
  color: rgba(34, 197, 94, .98);
  border-color: rgba(34, 197, 94, .24);
  background: rgba(34, 197, 94, .08);
}
.az-up-chip.delta{
  color: rgba(245, 158, 11, .98);
  border-color: rgba(245, 158, 11, .26);
  background: rgba(245, 158, 11, .08);
}
.az-up-chip.ts{
  color: rgba(255,255,255,.72);
  border-color: rgba(255,255,255,.10);
  background: rgba(255,255,255,.04);
}
.az-up-sub{
  margin-left: 38px;
  font-family: var(--az-mono);
  font-size: 12px;
  color: rgba(255,255,255,.56);
  word-break: break-word;
}

.rt-grid{ display:grid; grid-template-columns: 1fr 1fr; gap: 14px; align-items: stretch; }
@media (max-width: 900px){ .rt-grid{ grid-template-columns: 1fr; } }

.rt-box{
  border: 1px solid var(--az-border);
  border-radius: 10px;
  background: rgba(0,0,0,.10);
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.rt-box-h{
  padding: 10px 12px;
  font-weight: 900;
  border-bottom: 1px solid rgba(255,255,255,.08);
  color: rgba(255,255,255,.92);
}
.rt-table{ width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
.rt-table tr td{
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,.06);
  vertical-align: top;
}
.rt-table tr:last-child td{ border-bottom: none; }
.rt-k{ width: 132px; color: var(--az-muted); white-space: nowrap; }
.rt-v{ color: rgba(255,255,255,.92); font-family: var(--az-mono); word-break: break-word; width: 100%; }

.az-grid-3{ display:grid; grid-template-columns: .80fr 1.20fr; gap: var(--grid-gap); align-items: stretch; }
.az-grid-3 > .az-card{ height: 100%; }
@media (max-width: 1200px){ .az-grid-3{ grid-template-columns: 1fr; } }

.res-shell{ display:flex; flex-direction:column; gap:12px; }
.res-top{ display:grid; grid-template-columns: 1fr auto; gap:10px; align-items:end; }
.res-big{ font-size: 34px; font-weight: 950; line-height:1; }
.res-big .unit{ font-size: 15px; opacity:.72; margin-left: 4px; font-weight:800; }
.res-sub{ color: var(--az-muted); font-size: 13px; font-family: var(--az-mono); }
.res-pill{ display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; border:1px solid var(--az-border); background: rgba(255,255,255,.04); font-size:12px; font-weight:900; }
.res-grid{ display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
@media (max-width: 700px){ .res-grid{ grid-template-columns: 1fr; } }
.res-box{ border: 1px solid var(--az-border); border-radius: 12px; background: rgba(0,0,0,.12); padding: 12px; }
.res-box-h{ display:flex; align-items:center; justify-content:space-between; margin-bottom: 8px; font-weight:900; }
.res-box-h .mini{ color: var(--az-muted); font-size: 12px; font-weight:700; }
.res-bar{ height: 10px; width:100%; border-radius: 999px; overflow:hidden; background: rgba(255,255,255,.08); }
.res-bar > span{ display:block; height:100%; border-radius:999px; }
.res-bar-cpu > span{ background: linear-gradient(90deg, #22d3ee, #1e88e5); }
.res-bar-mem > span{ background: linear-gradient(90deg, #60a5fa, #a78bfa); }
.res-kpis{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin-top:8px; font-size: 13px; }
.res-kpis .v{ font-family: var(--az-mono); font-weight: 900; color: rgba(255,255,255,.92); }

.console-frame{
  height: 420px;
  overflow: auto;
  border: 1px solid var(--az-border);
  border-radius: 10px;
  background: rgba(0,0,0,.55) !important;
  padding: 10px 12px;
}
.console-frame, .console-frame * { background: transparent !important; }
.console-frame { background: rgba(0,0,0,.55) !important; }
.console-content{
  font-family: var(--az-mono) !important;
  font-size: 13px !important;
  line-height: 1.35 !important;
  color: rgba(255,255,255,.86) !important;
  white-space: pre-wrap !important;
  word-break: break-word !important;
  margin: 0 !important;
  padding: 0 !important;
}

.t-dim{ color: rgba(255,255,255,.45) !important; }
.t-info{ color: rgba(56, 189, 248, .95) !important; }
.t-warn{ color: rgba(245, 158, 11, .95) !important; }
.t-err{  color: rgba(239, 68, 68, .95) !important; }
.t-ok{   color: rgba(34, 197, 94, .95) !important; }
.t-vio{  color: rgba(167, 139, 250, .95) !important; }
.t-cyan{ color: rgba(34, 211, 238, .95) !important; }
.t-bold{ font-weight: 900 !important; }

.az-player{
  width: 100%;
  margin-top: 10px;
  padding: 10px 10px;
  border-radius: 12px;
  border: 1px solid var(--az-border);
  background: rgba(0,0,0,.22);
}
.az-player audio{
  width: 100%;
  height: 42px;
  filter: invert(1) hue-rotate(180deg) saturate(1.2);
  opacity: 0.95;
}
.az-player .hint{
  margin-top: 8px;
  font-size: 13px;
  color: rgba(255,255,255,.65);
  font-family: var(--az-mono);
}

.np-meta{
  margin-top: 8px;
  display:flex;
  flex-direction:column;
  gap: 6px;
}
.np-line{
  font-family: var(--az-mono);
  font-size: 13px;
  color: rgba(255,255,255,.80);
}
.np-k{ color: rgba(255,255,255,.55); }
.np-v{ color: rgba(255,255,255,.92); font-weight: 800; }
.np-pill{
  display:inline-flex; align-items:center; gap:8px;
  padding: 5px 10px;
  border-radius: 999px;
  border:1px solid var(--az-border);
  background: rgba(255,255,255,.05);
}

.az-tabsbar{
  margin: 10px 0 18px 0;
  border: 1px solid rgba(255,255,255,.10);
  border-radius: 12px;
  overflow: hidden;
}
.az-tabsbar .q-tabs{
  background: rgba(0,0,0,.15) !important;
}

/* SETTINGS UI */
.az-settings-toolbar{
  display:flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items:center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.az-settings-tools-left{
  display:flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items:center;
}

.az-settings-tools-right{
  display:flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items:center;
}

.az-settings-topcats{
  margin: 10px 0 12px 0;
  border: 1px solid rgba(255,255,255,.10);
  border-radius: 12px;
  overflow: hidden;
}
.az-settings-topcats .q-tabs{
  background: rgba(0,0,0,.18) !important;
}

.az-settings-grid{
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 1200px){
  .az-settings-grid{ grid-template-columns: 1fr; }
}

.set-box{
  border: 1px solid var(--az-border);
  border-radius: 12px;
  background: rgba(0,0,0,.10);
  overflow: hidden;
}
.set-box-h{
  padding: 10px 12px;
  font-weight: 950;
  border-bottom: 1px solid rgba(255,255,255,.08);
  display:flex;
  align-items:center;
  justify-content:space-between;
}
.set-box-h .meta{
  font-family: var(--az-mono);
  font-size: 12px;
  opacity:.75;
}
.set-box-b{
  padding: 6px 10px;
}

.set-row{
  display:grid;
  grid-template-columns: 520px 1fr;
  gap: 10px;
  padding: 10px 8px;
  border-bottom: 1px solid rgba(255,255,255,.06);
  align-items:flex-start;
}
.set-row:last-child{ border-bottom:none; }

.set-left{
  display:flex;
  flex-direction:column;
  gap: 4px;
  min-width: 0;
}

.set-name{
  font-size: 14px;
  font-weight: 900;
  color: rgba(255,255,255,.94);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.set-desc{
  font-size: 12px;
  color: var(--az-muted);
  line-height: 1.25;
  white-space: normal;
  word-break: break-word;
  opacity: .92;
}

.set-ctl{
  justify-self: end;
  width: 100%;
}

.az-inp .q-field__native,
.az-inp .q-field__input,
.az-inp input{
  color: rgba(255,255,255,.92) !important;
  font-family: var(--az-mono) !important;
}

/* SIMPLE LIVE PLAYER */
.az-stream-player{
  width: 100%;
  margin-top: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--az-border);
  background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(0,0,0,.18));
  box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
}
.az-stream-audio{
  display: none;
}
.az-stream-top{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.az-stream-live{
  display:inline-flex;
  align-items:center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(239,68,68,.12);
  border: 1px solid rgba(239,68,68,.28);
  color: rgba(255,255,255,.96);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: .04em;
}
.az-live-dot{
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: var(--az-red);
  box-shadow: 0 0 0 4px rgba(239,68,68,.18);
}
.az-stream-state{
  font-family: var(--az-mono);
  font-size: 12px;
  color: rgba(255,255,255,.68);
}
.az-stream-controls{
  display:flex;
  flex-wrap: wrap;
  align-items:center;
  gap: 10px;
}
.az-stream-btn{
  appearance: none;
  border: 1px solid rgba(255,255,255,.16);
  background: rgba(255,255,255,.05);
  color: rgba(255,255,255,.94);
  border-radius: 10px;
  padding: 8px 14px;
  font-weight: 900;
  cursor: pointer;
  transition: transform .12s ease, background .12s ease, border-color .12s ease;
}
.az-stream-btn:hover{
  transform: translateY(-1px);
  background: rgba(255,255,255,.08);
  border-color: rgba(255,255,255,.24);
}
.az-stream-btn.primary{
  background: linear-gradient(180deg, rgba(30,136,229,.96), rgba(21,101,192,.96));
  border-color: rgba(30,136,229,.65);
  color: #fff;
}
.az-stream-volume-wrap{
  display:inline-flex;
  align-items:center;
  gap: 10px;
  margin-left: auto;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,.08);
  background: rgba(0,0,0,.14);
}
.az-stream-vol-label{
  font-family: var(--az-mono);
  font-size: 12px;
  color: rgba(255,255,255,.72);
}
.az-stream-volume{
  width: 140px;
  accent-color: var(--az-blue);
}
.az-stream-hint{
  margin-top: 10px;
  font-size: 13px;
  color: rgba(255,255,255,.65);
  font-family: var(--az-mono);
  word-break: break-all;
}
"""
