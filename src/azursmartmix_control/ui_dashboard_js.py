from __future__ import annotations


AZURA_DASHBOARD_JS = r"""
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

  const API_BASE = String(window.azApiBase || '/api').replace(/\/+$/, '');

  function apiUrl(path){
    const p = String(path || '');
    if (!p) return API_BASE;
    return p.startsWith('/') ? (API_BASE + p) : (API_BASE + '/' + p);
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

    const bpmRuntimeNum = Number(now?.bpm_runtime);
    const bpmRuntime = Number.isFinite(bpmRuntimeNum) ? bpmRuntimeNum.toFixed(2) : '—';

    const predicted = now && typeof now.predicted_next === 'object' ? now.predicted_next : null;
    const predTitle = predicted ? String(predicted.title_display || predicted.title || '—') : '—';
    const predPl = predicted ? String(predicted.playlist || '—') : '—';

    const predBpmNum = Number(predicted?.bpm);
    const predBpm = Number.isFinite(predBpmNum) ? predBpmNum.toFixed(2) : '—';

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
      '<div class="np-line"><span class="np-k">playlist:</span> <span class="np-v" data-copy="' + esc(playlistEff) + '">' + esc(playlistEff) + '</span>' +
      ' <span class="t-dim">|</span> <span class="np-k">bpm:</span> <span class="np-v" data-copy="' + esc(bpmRuntime) + '">' + esc(bpmRuntime) + '</span></div>' +
      '<div class="np-line"><span class="np-k">next(pred):</span> <span class="np-v" data-copy="' + esc(predTitle) + '">' + esc(predTitle) + '</span>' +
      ' <span class="t-dim">|</span> <span class="np-k">pl:</span> <span class="np-v" data-copy="' + esc(predPl) + '">' + esc(predPl) + '</span>' +
      ' <span class="t-dim">|</span> <span class="np-k">bpm:</span> <span class="np-v" data-copy="' + esc(predBpm) + '">' + esc(predBpm) + '</span></div>' +
      '<div class="np-line">' + hint + '</div>' +
      '</div>'
    );
  }

  function detectUpcomingSource(it){
    const hasBpm = Number.isFinite(Number(it?.bpm));
    const hasDelta = Number.isFinite(Number(it?.delta_pct));
    if (hasDelta && !hasBpm) return 'tempo';
    if (hasBpm) return 'runtime';
    return 'mixed';
  }

  function upcomingSourceBadge(source){
    if (source === 'runtime') {
      return '<span class="az-up-badge runtime">RUNTIME</span>';
    }
    if (source === 'tempo') {
      return '<span class="az-up-badge tempo">TEMPO</span>';
    }
    return '<span class="az-up-badge">MERGED</span>';
  }

  function chip(cls, label, value){
    return '<span class="az-up-chip ' + esc(cls) + '"><span>' + esc(label) + '</span><span data-copy="' + esc(value) + '">' + esc(value) + '</span></span>';
  }

  function upcomingHTML(items){
    const arr = Array.isArray(items) ? items : [];
    if (!arr.length) {
      return '<div style="opacity:.7;">—</div>';
    }

    return arr.map((it, idx) => {
      const source = detectUpcomingSource(it);
      const title = String(it?.title_display || it?.title || '—');
      const playlist = String(it?.playlist || '').trim();
      const ts = String(it?.ts || '').trim();
      const fromTitle = String(it?.from_title || '').trim();

      const bpm = Number(it?.bpm);
      const bpmTxt = Number.isFinite(bpm) ? bpm.toFixed(2) : '';

      const delta = Number(it?.delta_pct);
      const deltaTxt = Number.isFinite(delta) ? delta.toFixed(2) + '%' : '';

      const metaParts = [];
      metaParts.push(upcomingSourceBadge(source));

      if (playlist) {
        metaParts.push(chip('playlist', 'PL', playlist));
      }
      if (bpmTxt) {
        metaParts.push(chip('bpm', 'BPM', bpmTxt));
      }
      if (deltaTxt) {
        metaParts.push(chip('delta', 'Δtempo', deltaTxt));
      }
      if (ts) {
        metaParts.push(chip('ts', 'TS', ts));
      }

      let sub = '';
      if (source === 'tempo' && fromTitle) {
        sub = '<div class="az-up-sub">transition from <span data-copy="' + esc(fromTitle) + '">' + esc(fromTitle) + '</span></div>';
      }

      return (
        '<div class="az-item">' +
          '<div class="az-up-item">' +
            '<div class="az-up-head">' +
              '<div class="az-up-idx">' + (idx + 1) + '.</div>' +
              '<div class="az-up-main">' +
                '<div class="az-up-title" data-copy="' + esc(title) + '">' + esc(title) + '</div>' +
                '<div class="az-up-meta">' + metaParts.join('') + '</div>' +
              '</div>' +
            '</div>' +
            sub +
          '</div>' +
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
    setText('np_sources', 'Sources: ' + String(now?.source || 'Icecast metadata only').trim());

    const upSource = upcoming && typeof upcoming.source === 'object' ? upcoming.source.primary : null;
    setText('up_source', String(upSource || 'engine_logs_tempo_accept_after_current'));
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

  async function fetchJSON(path){
    const u = apiUrl(path) + (String(path).includes('?') ? '&' : '?') + '_ts=' + Date.now();
    const r = await fetch(u, {
      method: 'GET',
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' },
    });
    if (!r.ok) throw new Error('http ' + r.status);
    return await r.json();
  }

  async function fetchText(path){
    const u = apiUrl(path) + (String(path).includes('?') ? '&' : '?') + '_ts=' + Date.now();
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
    state.mainTimer = null;
    state.logsTimer = null;
    void mainLoop();
    void logsLoop();
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
      void refreshMain();
      void refreshLogs();
    }
  });

  window.addEventListener('focus', () => {
    if (!state.running) return;
    void refreshMain();
  });

  window.setInterval(() => {
    if (state.running) updateSyncBadge('ok');
  }, 1000);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      startDashboard();
    }, { once: true });
  } else {
    startDashboard();
  }
})();
"""
