/**
 * DB Queue + Read Stats tabs — WebSocket live updates via core.bus.
 * Falls back to a 5 s REST poll if the WebSocket is unavailable.
 */
(function () {
  'use strict';

  var dbPanel    = document.getElementById('tab-db');
  var readsPanel = document.getElementById('tab-reads');
  if (!dbPanel) return;

  var urlDbStats = dbPanel.dataset.urlDbStats;
  var urlBus     = dbPanel.dataset.urlBus;

  // ── DOM references ────────────────────────────────────────────────────
  // Writer
  var elWritesTotal = document.getElementById('db-writes-total');
  var elWritesError = document.getElementById('db-writes-error');
  var elQueueDepth  = document.getElementById('db-queue-depth');
  var elP50         = document.getElementById('db-p50');
  var elP95         = document.getElementById('db-p95');
  var elP99         = document.getElementById('db-p99');
  // Attribution
  var elAttrBody    = document.getElementById('db-attr-body');
  // Private queues
  var elPrivBody    = document.getElementById('db-priv-body');
  // Reads
  var elReadsTotal  = document.getElementById('reads-total');
  var elReadsRows   = document.getElementById('reads-rows');
  var elReadsLastMs = document.getElementById('reads-last-ms');
  var elReadsAvgMs  = document.getElementById('reads-avg-ms');
  // Market buffer
  var elCacheHits   = document.getElementById('cache-hits');
  var elCacheMisses = document.getElementById('cache-misses');
  var elCacheRate   = document.getElementById('cache-rate');

  // ── Rendering ─────────────────────────────────────────────────────────
  function fmt(v) { return v != null ? Number(v).toLocaleString() : '—'; }
  function fmtF(v, d) { return v != null ? Number(v).toFixed(d || 1) : '—'; }

  function applyStats(data) {
    // Writer card
    var w = data.writer || {};
    if (elWritesTotal) elWritesTotal.textContent = fmt(w.writes_total);
    if (elWritesError) elWritesError.textContent = fmt(w.writes_error);
    if (elQueueDepth)  elQueueDepth.textContent  = fmt(w.queue_depth);
    if (elP50) elP50.textContent = fmtF(w.p50_ms);
    if (elP95) elP95.textContent = fmtF(w.p95_ms);
    if (elP99) elP99.textContent = fmtF(w.p99_ms);

    // Attribution table
    var attr = data.attribution || {};
    if (elAttrBody) {
      var attrKeys = Object.keys(attr);
      if (attrKeys.length === 0) {
        elAttrBody.innerHTML = '<tr><td colspan="3" class="muted">No active tasks</td></tr>';
      } else {
        var rows = '';
        attrKeys.forEach(function (tid) {
          var a = attr[tid];
          rows += '<tr><td class="mono">' + tid + '</td><td>' + fmt(a.ops) + '</td><td>' + fmt(a.rows) + '</td></tr>';
        });
        elAttrBody.innerHTML = rows;
      }
    }

    // Private queues table
    var priv = data.private_queues || {};
    if (elPrivBody) {
      var privKeys = Object.keys(priv);
      if (privKeys.length === 0) {
        elPrivBody.innerHTML = '<tr><td colspan="5" class="muted">No active private queues</td></tr>';
      } else {
        var prows = '';
        privKeys.forEach(function (oid) {
          var q = priv[oid];
          prows += '<tr><td class="mono">' + oid + '</td><td>' + fmt(q.ops) + '</td><td>' + fmt(q.rows) + '</td><td>' + fmt(q.queue_depth) + '</td><td>' + (q.thread_active ? '●' : '○') + '</td></tr>';
        });
        elPrivBody.innerHTML = prows;
      }
    }

    // Read stats
    var r = data.reads || {};
    if (elReadsTotal)  elReadsTotal.textContent  = fmt(r.reads_total);
    if (elReadsRows)   elReadsRows.textContent   = fmt(r.rows_total);
    if (elReadsLastMs) elReadsLastMs.textContent  = fmtF(r.last_latency_ms);
    var avg = (r.reads_total > 0 && r.latency_sum_ms != null) ? (r.latency_sum_ms / r.reads_total) : null;
    if (elReadsAvgMs)  elReadsAvgMs.textContent   = fmtF(avg);

    // Market buffer
    var mb = data.market_buffer || {};
    var hits   = mb.cache_hits || 0;
    var misses = mb.cache_misses || 0;
    if (elCacheHits)   elCacheHits.textContent   = fmt(hits);
    if (elCacheMisses) elCacheMisses.textContent = fmt(misses);
    var total  = hits + misses;
    if (elCacheRate)   elCacheRate.textContent    = total > 0 ? ((hits / total) * 100).toFixed(1) : '—';
  }

  // ── Initial fetch ─────────────────────────────────────────────────────
  function fetchOnce() {
    fetch(urlDbStats)
      .then(function (r) { return r.json(); })
      .then(applyStats)
      .catch(function () {});
  }
  fetchOnce();

  // ── WebSocket bus subscription ────────────────────────────────────────
  var wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var wsUrl = wsProtocol + '//' + location.host + urlBus;
  var ws = null;
  var fallbackTimer = null;

  function startWS() {
    try { ws = new WebSocket(wsUrl); } catch (e) { startFallback(); return; }

    ws.onopen = function () {
      ws.send(JSON.stringify({ action: 'subscribe', topics: ['db/stats'] }));
      if (fallbackTimer) { clearInterval(fallbackTimer); fallbackTimer = null; }
    };

    ws.onmessage = function (ev) {
      try {
        var msg = JSON.parse(ev.data);
        if (msg.type === 'publish' && msg.topic === 'db/stats' && msg.data) {
          applyStats(msg.data);
        }
      } catch (e) {}
    };

    ws.onclose = function () { setTimeout(startWS, 5000); };
    ws.onerror = function () { ws.close(); };
  }

  function startFallback() {
    if (!fallbackTimer) {
      fallbackTimer = setInterval(fetchOnce, 5000);
    }
  }

  startWS();
}());
