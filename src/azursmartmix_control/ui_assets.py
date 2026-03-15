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
.az-item{ padding: 10px 12px; border-radius: 10px; border: 1px solid var(--az-border); background: rgba(255,255,255,.04); }
.az-item .idx{ display:inline-block; min-width:24px; font-weight:950; color: rgba(255,255,255,.75); }
.az-item .txt{ font-weight:650; }

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

AZURA_JS = r"""
document.addEventListener('click', (ev) => {
  const el = ev.target.closest('[data-copy]');
  if (!el) return;
  const txt = el.getAttribute('data-copy') || el.textContent || '';
  if (!txt) return;
  navigator.clipboard.writeText(txt).catch(()=>{});
});

(function(){
  function esc(value){
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function setHTML(id, html){
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  function setText(id, text){
    const el = document.getElementById(id);
    if (el) el.textContent = String(text ?? '');
  }

  function fmtBytesGb(value){
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return '0.00 GB';
    return (n / (1024 ** 3)).toFixed(2) + ' GB';
  }

  function runtimeTableHTML(data){
    const x = data && typeof data === 'object' ? data : {};
    const rows = [
      ['name', x.name ?? '—'],
      ['image', x.image ?? '—'],
      ['status', x.status ?? '—'],
      ['health', x.health ?? '-'],
      ['uptime', x.uptime ?? '-'],
    ];
    return '<table class="rt-table">' + rows.map(([k, v]) => (
      '<tr><td class="rt-k">' + esc(k) + '</td><td class="rt-v" data-copy="' + esc(v) + '">' + esc(v) + '</td></tr>'
    )).join('') + '</table>';
  }

  function resourcesCPUHTML(data){
    const cpu = data && typeof data.cpu === 'object' ? data.cpu : {};
    const loadavg = data && typeof data.loadavg === 'object' ? data.loadavg : {};
    const pct = Number(cpu.percent);
    const pctNum = Number.isFinite(pct) ? pct : 0.0;
    const pctTxt = Number.isFinite(pct) ? pctNum.toFixed(2) : '—';
    const l1 = Number(loadavg.one);
    const l5 = Number(loadavg.five);
    const loadTxt = Number.isFinite(l1) && Number.isFinite(l5) ? (l1.toFixed(2) + ' / ' + l5.toFixed(2)) : '—';
    const width = Math.max(0, Math.min(100, pctNum));

    return (
      '<div class="res-box">' +
      '<div class="res-box-h"><span>CPU</span><span class="mini">load 1/5m</span></div>' +
      '<div class="res-top">' +
      '<div class="res-big">' + esc(pctTxt) + '<span class="unit">%</span></div>' +
      '<div class="res-sub">' + esc(loadTxt) + '</div>' +
      '</div>' +
      '<div class="res-bar res-bar-cpu"><span style="width:' + width.toFixed(2) + '%;"></span></div>' +
      '<div class="res-kpis">' +
      '<div><span class="t-dim">sample</span> <span class="v">' + esc(cpu.sample ?? '—') + '</span></div>' +
      '<div><span class="t-dim">source</span> <span class="v">' + esc(data?.source ?? '—') + '</span></div>' +
      '</div>' +
      '</div>'
    );
  }

  function resourcesMemHTML(data){
    const mem = data && typeof data.memory === 'object' ? data.memory : {};
    const pct = Number(mem.used_percent);
    const pctNum = Number.isFinite(pct) ? pct : 0.0;
    const pctTxt = Number.isFinite(pct) ? pctNum.toFixed(2) : '—';
    const width = Math.max(0, Math.min(100, pctNum));

    return (
      '<div class="res-box">' +
      '<div class="res-box-h"><span>Memory</span><span class="mini">used / total</span></div>' +
      '<div class="res-top">' +
      '<div class="res-big">' + esc(fmtBytesGb(mem.used_bytes)) + '</div>' +
      '<div class="res-sub">' + esc(pctTxt) + '%</div>' +
      '</div>' +
      '<div class="res-bar res-bar-mem"><span style="width:' + width.toFixed(2) + '%;"></span></div>' +
      '<div class="res-grid">' +
      '<div class="res-kpis"><div><span class="t-dim">total</span> <span class="v">' + esc(fmtBytesGb(mem.total_bytes)) + '</span></div><div><span class="t-dim">avail</span> <span class="v">' + esc(fmtBytesGb(mem.available_bytes)) + '</span></div></div>' +
      '<div class="res-kpis"><div><span class="t-dim">cached</span> <span class="v">' + esc(fmtBytesGb(mem.cached_bytes)) + '</span></div><div><span class="t-dim">used</span> <span class="v">' + esc(pctTxt) + '%</span></div></div>' +
      '</div>' +
      '</div>'
    );
  }

  function nowMetaHTML(now){
    const playlistEff = now?.playlist_effective ? String(now.playlist_effective) : '—';
    const predicted = now && typeof now.predicted_next === 'object' ? now.predicted_next : null;
    const predTitle = predicted ? String(predicted.title_display || predicted.title || '—') : '—';
    const predPl = predicted ? String(predicted.playlist || '—') : '—';

    const ss = now && typeof now.engine_stream_start === 'object' ? now.engine_stream_start : null;
    let hint = '';
    if (ss && ss.ok && ss.recent) {
      const ageTxt = Number.isInteger(ss.age_s) ? (String(ss.age_s) + 's') : 'recent';
      hint = '<span class="np-pill"><span class="t-ok t-bold">STREAM_START</span><span class="t-dim">(' + esc(ageTxt) + ')</span></span>';
    } else if (ss && ss.ok && ss.line) {
      const ageTxt = Number.isInteger(ss.age_s) ? (String(ss.age_s) + 's') : '';
      hint = '<span class="np-pill"><span class="t-dim">last STREAM_START</span><span class="t-dim">' + esc(ageTxt) + '</span></span>';
    }

    return (
      '<div class="np-meta">' +
      '<div class="np-line"><span class="np-k">playlist:</span> <span class="np-v" data-copy="' + esc(playlistEff) + '">' + esc(playlistEff) + '</span></div>' +
      '<div class="np-line"><span class="np-k">next(pred):</span> <span class="np-v" data-copy="' + esc(predTitle) + '">' + esc(predTitle) + '</span>' +
      ' <span class="t-dim">|</span> <span class="np-k">pl:</span> <span class="np-v" data-copy="' + esc(predPl) + '">' + esc(predPl) + '</span></div>' +
      '<div class="np-line">' + hint + '</div>' +
      '</div>'
    );
  }

  function upcomingHTML(items){
    const arr = Array.isArray(items) ? items : [];
    if (!arr.length) {
      return '<div style="opacity:.7;">—</div>';
    }

    return arr.map((it, idx) => {
      const title = String(it?.title_display || it?.title || '—');
      const playlist = String(it?.playlist || '—');
      const ts = String(it?.ts || '');
      const delta = Number(it?.delta_pct);
      const deltaTxt = Number.isFinite(delta) ? delta.toFixed(2) + '%' : '';

      const parts = [];
      if (playlist && playlist !== '—') {
        parts.push('<span class="t-cyan t-bold" data-copy="' + esc(playlist) + '">' + esc(playlist) + '</span>');
      }
      if (deltaTxt) {
        parts.push('<span class="t-dim">Δ</span> <span class="t-ok t-bold">' + esc(deltaTxt) + '</span>');
      }
      if (ts) {
        parts.push('<span class="t-dim">[' + esc(ts) + ']</span>');
      }

      const tail = parts.length ? (' <span class="t-dim">|</span> ' + parts.join(' ')) : '';

      return (
        '<div class="az-item"><span class="idx">' + (idx + 1) + '.</span> ' +
        '<span class="txt" data-copy="' + esc(title) + '">' + esc(title) + '</span>' +
        tail +
        '</div>'
      );
    }).join('');
  }

  function logsHTML(text){
    return '<div class="console-content">' + esc(text || '—') + '</div>';
  }

  function syncBadgeHTML(state, ageSec){
    const safeAge = Number.isFinite(ageSec) ? Math.max(0, ageSec) : 0;
    if (state === 'ok') {
      return '<span class="az-badge"><span class="az-dot ok"></span><span>Sync: ' + safeAge.toFixed(0) + 's</span></span>';
    }
    if (state === 'warn') {
      return '<span class="az-badge" style="border-color: rgba(245,158,11,.55); background: rgba(245,158,11,.15);"><span class="az-dot warn"></span><span>Sync delayed</span></span>';
    }
    return '<span class="az-badge" style="border-color: rgba(239,68,68,.55); background: rgba(239,68,68,.15);"><span class="az-dot err"></span><span>Sync error</span></span>';
  }

  function applyMainPayload(payload){
    const resources = payload?.resources ?? {};
    const runtime = payload?.runtime ?? {};
    const now = payload?.now ?? {};
    const upcoming = payload?.upcoming ?? {};

    setHTML('res_host_meta', '<span class="res-pill">source: ' + esc(resources.source || 'host') + '</span>');
    setHTML('res_cpu_html', resourcesCPUHTML(resources));
    setHTML('res_mem_html', resourcesMemHTML(resources));

    setHTML(
      'docker_badge',
      '<span class="az-badge"><span class="az-dot ' + (runtime?.docker_ping ? 'ok' : 'err') + '"></span><span>Docker: ' + (runtime?.docker_ping ? 'OK' : 'DOWN') + '</span></span>'
    );
    setHTML('rt_engine_tbl', runtimeTableHTML(runtime.engine || {}));
    setHTML('rt_sched_tbl', runtimeTableHTML(runtime.scheduler || {}));

    setText('np_title', now?.title_effective || now?.title_observed || '—');
    setHTML('np_meta', nowMetaHTML(now));
    setText('np_sources', 'Sources: ' + String(now?.source || 'Icecast metadata + engine tempo(select)').trim());

    const upSource = upcoming && typeof upcoming.source === 'object' ? upcoming.source.primary : null;
    setText('up_source', String(upSource || 'from engine tempo(select) log'));
    setHTML('upcoming_list', upcomingHTML(upcoming?.upcoming || []));
  }

  function applyLogs(engineText, schedulerText){
    setHTML('log_engine', logsHTML(engineText));
    setHTML('log_sched', logsHTML(schedulerText));
  }

  const state = {
    running: false,
    mainInflight: false,
    logsInflight: false,
    mainTimer: null,
    logsTimer: null,
    lastOkTs: 0,
  };

  async function fetchJSON(url){
    const u = url + (url.includes('?') ? '&' : '?') + '_ts=' + Date.now();
    const r = await fetch(u, {
      method: 'GET',
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' },
    });
    if (!r.ok) throw new Error('http ' + r.status);
    return await r.json();
  }

  async function fetchText(url){
    const u = url + (url.includes('?') ? '&' : '?') + '_ts=' + Date.now();
    const r = await fetch(u, {
      method: 'GET',
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' },
    });
    if (!r.ok) throw new Error('http ' + r.status);
    return await r.text();
  }

  function updateSyncBadge(kind){
    const now = Date.now();
    const ageSec = state.lastOkTs > 0 ? (now - state.lastOkTs) / 1000.0 : 0;
    if (kind === 'error') {
      setHTML('client_sync_badge', syncBadgeHTML('error', ageSec));
      return;
    }
    if (kind === 'warn' || ageSec > 12) {
      setHTML('client_sync_badge', syncBadgeHTML('warn', ageSec));
      return;
    }
    setHTML('client_sync_badge', syncBadgeHTML('ok', ageSec));
  }

  async function refreshMain(){
    if (state.mainInflight) return;
    state.mainInflight = true;

    try {
      const payload = await fetchJSON('/panel/dashboard?upcoming_n=10');
      applyMainPayload(payload);
      state.lastOkTs = Date.now();
      updateSyncBadge('ok');
    } catch (err) {
      console.warn('dashboard main refresh failed', err);
      updateSyncBadge('error');
    } finally {
      state.mainInflight = false;
    }
  }

  async function refreshLogs(){
    if (state.logsInflight) return;
    state.logsInflight = true;

    try {
      const [engineText, schedulerText] = await Promise.all([
        fetchText('/logs?service=engine&tail=200'),
        fetchText('/logs?service=scheduler&tail=200'),
      ]);
      applyLogs(engineText, schedulerText);
    } catch (err) {
      console.warn('dashboard logs refresh failed', err);
    } finally {
      state.logsInflight = false;
    }
  }

  function mainDelayMs(){
    return document.hidden ? 10000 : 4000;
  }

  function logsDelayMs(){
    return document.hidden ? 25000 : 12000;
  }

  async function mainLoop(){
    if (!state.running) return;
    await refreshMain();
    clearTimeout(state.mainTimer);
    state.mainTimer = window.setTimeout(mainLoop, mainDelayMs());
  }

  async function logsLoop(){
    if (!state.running) return;
    await refreshLogs();
    clearTimeout(state.logsTimer);
    state.logsTimer = window.setTimeout(logsLoop, logsDelayMs());
  }

  function startDashboard(){
    if (state.running) return;
    state.running = true;
    clearTimeout(state.mainTimer);
    clearTimeout(state.logsTimer);
    mainLoop();
    logsLoop();
  }

  function stopDashboard(){
    state.running = false;
    clearTimeout(state.mainTimer);
    clearTimeout(state.logsTimer);
    state.mainTimer = null;
    state.logsTimer = null;
    updateSyncBadge('warn');
  }

  window.azDashboardStart = startDashboard;
  window.azDashboardStop = stopDashboard;
  window.azDashboardRefreshNow = async function(){
    await refreshMain();
    await refreshLogs();
  };

  document.addEventListener('visibilitychange', () => {
    if (!state.running) return;
    if (!document.hidden) {
      refreshMain();
      refreshLogs();
    }
  });

  window.addEventListener('focus', () => {
    if (!state.running) return;
    refreshMain();
  });

  window.setInterval(() => {
    if (state.running) updateSyncBadge('ok');
  }, 1000);

  window.addEventListener('load', () => {
    startDashboard();
  });
})();

(function(){
  function findPlayer(playerId){
    const root = document.getElementById(playerId);
    if (!root) return null;
    const audio = root.querySelector('.az-stream-audio');
    const state = root.querySelector('[data-role="state"]');
    if (!audio || !state) return null;
    return { root, audio, state };
  }

  function stampUrl(baseUrl){
    try{
      const u = new URL(baseUrl, window.location.href);
      u.searchParams.set('_ts', String(Date.now()));
      return u.toString();
    }catch(_e){
      const sep = baseUrl.includes('?') ? '&' : '?';
      return `${baseUrl}${sep}_ts=${Date.now()}`;
    }
  }

  function setState(stateEl, text){
    if (stateEl) stateEl.textContent = text;
  }

  function bindOnce(ctx){
    if (!ctx || ctx.audio.dataset.bound === '1') return;
    ctx.audio.dataset.bound = '1';

    ctx.audio.addEventListener('playing', () => setState(ctx.state, 'playing'));
    ctx.audio.addEventListener('pause', () => {
      if (!ctx.audio.src) {
        setState(ctx.state, 'idle');
        return;
      }
      setState(ctx.state, 'paused');
    });
    ctx.audio.addEventListener('waiting', () => setState(ctx.state, 'buffering'));
    ctx.audio.addEventListener('stalled', () => setState(ctx.state, 'stalled'));
    ctx.audio.addEventListener('loadstart', () => setState(ctx.state, 'connecting'));
    ctx.audio.addEventListener('emptied', () => setState(ctx.state, 'idle'));
    ctx.audio.addEventListener('error', () => setState(ctx.state, 'error'));
  }

  window.azStreamPlay = async function(playerId){
    const ctx = findPlayer(playerId);
    if (!ctx) return;
    bindOnce(ctx);

    const baseUrl = ctx.root.getAttribute('data-stream-url') || '';
    if (!baseUrl) {
      setState(ctx.state, 'missing-url');
      return;
    }

    const nextUrl = stampUrl(baseUrl);

    try{
      if (ctx.audio.src !== nextUrl) {
        ctx.audio.src = nextUrl;
      }
      ctx.audio.load();
      setState(ctx.state, 'connecting');
      await ctx.audio.play();
    }catch(_e){
      setState(ctx.state, 'blocked');
    }
  };

  window.azStreamStop = function(playerId){
    const ctx = findPlayer(playerId);
    if (!ctx) return;
    bindOnce(ctx);

    try{
      ctx.audio.pause();
      ctx.audio.removeAttribute('src');
      ctx.audio.load();
    }catch(_e){}
    setState(ctx.state, 'stopped');
  };

  window.azStreamToggleMute = function(playerId){
    const ctx = findPlayer(playerId);
    if (!ctx) return;
    bindOnce(ctx);

    ctx.audio.muted = !ctx.audio.muted;
    setState(ctx.state, ctx.audio.muted ? 'muted' : (ctx.audio.paused ? 'paused' : 'playing'));
  };

  window.azStreamSetVolume = function(playerId, value){
    const ctx = findPlayer(playerId);
    if (!ctx) return;
    bindOnce(ctx);

    const n = Number(value);
    if (!Number.isFinite(n)) return;
    const vol = Math.max(0, Math.min(100, n)) / 100.0;
    ctx.audio.volume = vol;
    if (vol > 0 && ctx.audio.muted) {
      ctx.audio.muted = false;
    }
  };
})();
"""
