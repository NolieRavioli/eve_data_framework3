/**
 * ESI Admin Queue — live rate cards via /esi/admin/ws WebSocket.
 * Admin-only: shows global (unfiltered) rate limiter data.
 */
(function () {
  'use strict';

  var esiCard   = document.getElementById('esi-rate-card');
  var esiGroups = document.getElementById('esi-groups');
  var esiReqs   = document.getElementById('esi-reqs');
  if (!esiCard) return;

  var _URL_WS_RATE = esiCard.dataset.urlWsRate || '/esi/admin/ws';

  function applyRateStats(s) {
    if (!s || s.requests_total === 0) return;
    esiCard.style.display = '';
    esiReqs.textContent = s.requests_total.toLocaleString() + ' req total';

    var groups = s.groups || {};
    Object.keys(groups).forEach(function (gname) {
      var g             = groups[gname];
      var effectiveUsed = (g.tokens_remaining != null && g.tokens_limit > 0)
                          ? Math.max(0, g.tokens_limit - g.tokens_remaining)
                          : (g.tokens_used || 0);
      var wspec  = g.tokens_limit + '/' + (g.window_str || g.window_seconds + 's');
      var pct    = g.tokens_limit > 0 ? (effectiveUsed / g.tokens_limit * 100) : 0;
      var col    = pct >= 90 ? 'var(--bad)' : pct >= 70 ? 'var(--warn)' : 'var(--accent)';
      var elId   = 'esi-grp-' + gname;
      var el     = document.getElementById(elId);
      if (effectiveUsed === 0) {
        if (el) el.remove();
        return;
      }
      if (!el) {
        el = document.createElement('div');
        el.id = elId;
        el.style.cssText = 'min-width:160px;flex:1;background:rgba(0,0,0,0.25);border-radius:6px;padding:0.5rem 0.75rem';
        esiGroups.appendChild(el);
      }
      el.innerHTML =
        '<div style="margin-bottom:0.35rem">' +
          '<span class="mono" style="font-size:0.82rem;color:var(--txt);font-weight:600">' + wspec + '</span>' +
          '<span class="muted" style="font-size:0.68rem;margin-left:0.45rem">&middot; ' + gname + '</span>' +
        '</div>' +
        '<div style="background:rgba(255,255,255,0.08);border-radius:999px;height:6px;overflow:hidden;margin-bottom:0.35rem">' +
          '<div style="height:100%;border-radius:999px;width:' + pct.toFixed(1) + '%;background:' + col + ';transition:width 0.5s"></div>' +
        '</div>' +
        '<div style="display:flex;justify-content:space-between;font-size:0.7rem">' +
          '<span class="muted">' + effectiveUsed.toLocaleString() + ' used</span>' +
          '<span class="muted">' + (g.tokens_remaining != null ? g.tokens_remaining.toLocaleString() : '\u2014') + ' / ' + g.tokens_limit.toLocaleString() + ' remaining</span>' +
        '</div>';
    });
  }

  (function openAdminWS() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws;
    try { ws = new WebSocket(proto + '//' + location.host + _URL_WS_RATE); }
    catch (e) { return; }

    ws.onmessage = function (ev) {
      try {
        var msg = JSON.parse(ev.data);
        if (msg.type !== 'publish') return;
        if (msg.topic === 'esi/rate' && msg.data) {
          applyRateStats(msg.data);
        }
      } catch (e) {}
    };
    ws.onclose = function () { setTimeout(openAdminWS, 5000); };
    ws.onerror = function () { ws.close(); };
  }());
}());
