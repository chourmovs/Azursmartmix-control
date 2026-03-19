from __future__ import annotations


AZURA_PLAYER_JS = r"""
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
