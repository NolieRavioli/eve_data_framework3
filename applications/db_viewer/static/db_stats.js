/**
 * db_stats.js — Live DB-unit stats via WebSocket for the /db and /db/admin pages.
 *
 * Expects a page-level <div id="db-stats-app"> with data attributes:
 *   data-ws-url      — WebSocket URL (/db/ws or /db/admin/ws)
 *   data-owner-id    — current owner_id (personal page only; empty for admin page)
 */
(function () {
  'use strict';

  var appEl = document.getElementById('db-stats-app');
  if (!appEl) return;

  var wsRelPath  = appEl.dataset.wsUrl;
  var currentOwner = parseInt(appEl.dataset.ownerId || '0', 10);
  var isAdmin    = appEl.dataset.isAdmin === '1';

  // ── Op-type display config ─────────────────────────────────────────────────
  var OP_TYPES = [
    { key: 'inserts',    label: 'INSERT',     weight_key: 'insert' },
    { key: 'upserts',    label: 'UPSERT',     weight_key: 'upsert' },
    { key: 'updates',    label: 'UPDATE',     weight_key: 'update' },
    { key: 'deletes',    label: 'DELETE',     weight_key: 'delete' },
    { key: 'truncates',  label: 'TRUNCATE',   weight_key: 'truncate' },
    { key: 'ddls',       label: 'DDL',        weight_key: 'ddl' },
    { key: 'bulk_loads', label: 'BULK LOAD',  weight_key: 'bulk_load' },
    { key: 'reads',      label: 'READ',       weight_key: 'read' },
  ];

  // ── Helper: format a number as a compact integer string ───────────────────
  function fmt(n) { return (n || 0).toLocaleString(); }
  function fmtF(n) { return (+(n || 0)).toFixed(2); }

  // ── Update overview cards ──────────────────────────────────────────────────
  function updateCards(totals, weights) {
    OP_TYPES.forEach(function (op) {
      var count = totals[op.key] || 0;
      var units = count * (weights[op.weight_key] || 0);
      var cardCount = document.getElementById('stat-count-' + op.key);
      var cardUnits = document.getElementById('stat-units-' + op.key);
      if (cardCount) cardCount.textContent = fmt(count);
      if (cardUnits) cardUnits.textContent = fmtF(units);
    });
    var totalUnitsEl = document.getElementById('stat-total-db-units');
    if (totalUnitsEl) totalUnitsEl.textContent = fmtF(totals.db_units || 0);
    var totalRowsEl  = document.getElementById('stat-total-rows');
    if (totalRowsEl)  totalRowsEl.textContent  = fmt(totals.rows || 0);
  }

  // ── Update per-task (personal) or per-owner (admin) table ─────────────────
  function updateTable(data, weights) {
    var tbody = document.getElementById('db-stats-tbody');
    if (!tbody) return;

    var rows = [];
    if (isAdmin) {
      // data = owner_totals dict
      Object.keys(data).forEach(function (ownerKey) {
        var bucket = data[ownerKey];
        rows.push({ label: ownerKey === 'SYSTEM' ? 'SYSTEM' : 'Owner ' + ownerKey, bucket: bucket });
      });
      rows.sort(function (a, b) { return (b.bucket.db_units || 0) - (a.bucket.db_units || 0); });
    } else {
      // data = attribution dict filtered to current owner
      Object.keys(data).forEach(function (tid) {
        var entry = data[tid];
        if (entry.owner_id !== currentOwner) return;
        rows.push({ label: (entry.task_name || tid) + ' [' + (entry.task_status || '?') + ']', bucket: entry });
      });
      rows.sort(function (a, b) { return (b.bucket.rows || 0) - (a.bucket.rows || 0); });
    }

    var html = '';
    rows.forEach(function (r) {
      var b = r.bucket;
      html += '<tr>';
      html += '<td>' + r.label + '</td>';
      OP_TYPES.forEach(function (op) {
        html += '<td class="num">' + fmt(b[op.key]) + '</td>';
      });
      html += '<td class="num">' + fmt(b.rows) + '</td>';
      html += '<td class="num db-units">' + fmtF(b.db_units) + '</td>';
      html += '</tr>';
    });
    tbody.innerHTML = html || '<tr><td colspan="11" class="empty-row">No activity since last restart.</td></tr>';
  }

  // ── Handle incoming db/stats payload ──────────────────────────────────────
  function applyPayload(data) {
    var weights     = data.weights      || {};
    var attribution = data.attribution  || {};
    var ownerTotals = data.owner_totals || {};

    if (isAdmin) {
      // Use global totals (sum of all owner_totals)
      var globalTotals = {};
      ['inserts','upserts','updates','deletes','truncates','ddls','bulk_loads','reads','rows'].forEach(function(k){
        globalTotals[k] = 0;
      });
      globalTotals.db_units = 0;
      Object.values(ownerTotals).forEach(function(bucket){
        Object.keys(globalTotals).forEach(function(k){ globalTotals[k] += (bucket[k] || 0); });
      });
      updateCards(globalTotals, weights);
      updateTable(ownerTotals, weights);
    } else {
      // Filter attribution to this owner's tasks
      var myAttribution = {};
      Object.keys(attribution).forEach(function(tid){
        if (attribution[tid].owner_id === currentOwner) {
          myAttribution[tid] = attribution[tid];
        }
      });
      var ownerKey = String(currentOwner);
      var myTotals = ownerTotals[ownerKey] || {};
      updateCards(myTotals, weights);
      updateTable(myAttribution, weights);
    }
  }

  // ── WebSocket connection ───────────────────────────────────────────────────
  var wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var wsUrl   = wsProto + '//' + location.host + wsRelPath;
  var ws;

  function startWS() {
    try { ws = new WebSocket(wsUrl); } catch (e) { return; }

    ws.onmessage = function (ev) {
      try {
        var msg = JSON.parse(ev.data);
        if (msg.type === 'publish' && msg.topic === 'db/stats' && msg.data) {
          applyPayload(msg.data);
        }
      } catch (e) {}
    };

    ws.onclose = function () { setTimeout(startWS, 5000); };
    ws.onerror = function () { try { ws.close(); } catch(e){} };
  }

  startWS();
}());
