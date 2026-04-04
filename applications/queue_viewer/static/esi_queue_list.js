function cancelTask(taskId, button) {
  var _esiCard = document.getElementById('esi-rate-card');
  fetch(_esiCard.dataset.urlCancel.replace('PLACEHOLDER', taskId), { method: 'POST' })
    .then(function (response) { return response.json(); })
    .then(function (payload) {
      if (!payload.cancelled) {
        if (payload.message) alert(payload.message);
        return;
      }
      var row = document.getElementById('row-' + taskId);
      if (row) {
        var badge = row.querySelector('.bdg');
        if (badge) { badge.textContent = 'cancelled'; badge.className = 'bdg bdg-warn'; }
      }
      if (button) button.remove();
    });
}

function clearDone() {
  var _esiCard = document.getElementById('esi-rate-card');
  fetch(_esiCard.dataset.urlClear, { method: 'POST' })
    .then(function (response) { return response.json(); })
    .then(function () { location.reload(); });
}

(function () {
  // Live ESI rate card - SSE push from /queue/rate_stream
  var esiCard   = document.getElementById('esi-rate-card');
  var esiGroups = document.getElementById('esi-groups');
  var esiReqs   = document.getElementById('esi-reqs');
  var isAdmin   = esiCard ? esiCard.dataset.isAdmin === 'true' : false;
  var _URL_RATE_STREAM = esiCard ? esiCard.dataset.urlRateStream : '/queue/rate_stream';

  function applyRateStats(d) {
    var s = d.limiter;
    if (!s || s.requests_total === 0) return;
    esiCard.style.display = '';
    esiReqs.textContent = s.requests_total.toLocaleString() + ' req total';

    // Render one tile per floating window
    var groups = s.groups || {};
    var runningTask = (d.tasks || []).find(function (t) { return t.status === 'running'; });
    Object.keys(groups).forEach(function (gname) {
      var g             = groups[gname];
      var effectiveUsed = (g.tokens_remaining != null && g.tokens_limit > 0)
                          ? Math.max(0, g.tokens_limit - g.tokens_remaining)
                          : (g.tokens_used || 0);
      var wspec  = g.tokens_limit + '/' + (g.window_str || g.window_seconds + 's');
      var pct    = g.tokens_limit > 0 ? (effectiveUsed / g.tokens_limit * 100) : 0;
      var col    = pct >= 90 ? 'var(--bad)' : pct >= 70 ? 'var(--warn)' : 'var(--accent)';
      var charName = (isAdmin && runningTask && runningTask.char_name) ? runningTask.char_name : '';
      // Hide buckets with no activity
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
          (charName ? '<span class="muted" style="font-size:0.68rem;margin-left:0.45rem">&middot; ' + charName + '</span>' : '') +
          '<span class="muted" style="font-size:0.68rem;margin-left:0.45rem">&middot; ' + gname + '</span>' +
        '</div>' +
        '<div style="background:rgba(255,255,255,0.08);border-radius:999px;height:6px;overflow:hidden;margin-bottom:0.35rem">' +
          '<div style="height:100%;border-radius:999px;width:' + pct.toFixed(1) + '%;background:' + col + ';transition:width 0.5s"></div>' +
        '</div>' +
        '<div style="display:flex;justify-content:space-between;font-size:0.7rem">' +
          '<span class="muted">' + effectiveUsed.toLocaleString() + ' used</span>' +
          '<span class="muted">' + (g.tokens_remaining != null ? g.tokens_remaining.toLocaleString() : '—') + ' / ' + g.tokens_limit.toLocaleString() + ' remaining</span>' +
        '</div>';
    });

    // Live-update every row from the tasks snapshot
    (d.tasks || []).forEach(function (t) {
      var row = document.getElementById('row-' + t.task_id);
      if (!row) return;

      // Status badge
      var badge = row.querySelector('.bdg');
      if (badge) {
        badge.textContent = t.status;
        badge.className = 'bdg' + (
          t.status === 'complete' ? ' bdg-ok' :
          t.status === 'failed'   ? ' bdg-bad' :
          t.status === 'running'  ? ' bdg-blue' : ' bdg-warn'
        );
      }

      // Queue badge
      var qBadge = row.querySelector('[data-col="queue"]');
      if (qBadge) {
        qBadge.textContent = t.queue || 'private';
        qBadge.className   = 'bdg' + (t.queue === 'public' ? ' bdg-blue' : '');
      }

      // Timestamps
      var startedEl  = row.querySelector('[data-col="started"]');
      var finishedEl = row.querySelector('[data-col="finished"]');
      if (startedEl  && t.started_at)  startedEl.textContent  = t.started_at;
      if (finishedEl && t.finished_at) finishedEl.textContent = t.finished_at;

      // ESI rate mini-bar
      var cell = row.querySelector('.esi-rate-cell');
      if (cell && t.esi_rate) {
        var r            = t.esi_rate;
        var effectiveUsed = r.tokens_limit > 0
                            ? Math.max(0, r.tokens_limit - (r.tokens_remaining || 0))
                            : (r.tokens_used || 0);
        var p   = r.tokens_limit > 0 ? (effectiveUsed / r.tokens_limit * 100) : 0;
        var bar = cell.querySelector('.esi-mini-bar');
        var lbl = cell.querySelector('.esi-mini-label');
        if (!bar) {
          cell.innerHTML =
            '<div style="width:90px;background:rgba(0,0,0,0.35);border-radius:999px;height:5px;overflow:hidden;margin-bottom:0.3rem">' +
              '<div class="esi-mini-bar" style="height:100%;border-radius:999px;width:0%;background:var(--accent)"></div>' +
            '</div>' +
            '<span class="esi-mini-label mono" style="font-size:0.68rem;color:var(--muted)"></span>';
          bar = cell.querySelector('.esi-mini-bar');
          lbl = cell.querySelector('.esi-mini-label');
        }
        if (bar) {
          bar.style.width      = p.toFixed(1) + '%';
          bar.style.background = p >= 90 ? 'var(--bad)' : p >= 70 ? 'var(--warn)' : 'var(--accent)';
        }
        if (lbl) lbl.textContent =
          r.requests_total.toLocaleString() + ' req  ' +
          effectiveUsed.toLocaleString() + '/' + r.tokens_limit.toLocaleString();
      }

      // Cancel button visibility
      var actionCell = row.querySelector('[data-col="action"]');
      if (actionCell) {
        var cancelBtn = actionCell.querySelector('.cancel-btn');
        if (t.status === 'pending' && !cancelBtn) {
          var btn = document.createElement('button');
          btn.className = 'btn btn-g cancel-btn';
          btn.style.cssText = 'padding:0.3rem 0.65rem;font-size:0.72rem';
          btn.textContent = 'Cancel';
          (function (tid, b) { b.onclick = function () { cancelTask(tid, b); }; }(t.task_id, btn));
          actionCell.insertBefore(btn, actionCell.firstChild);
        } else if (t.status !== 'pending' && cancelBtn) {
          cancelBtn.remove();
        }
      }
    });
  }

  (function openRateStream() {
    var es = new EventSource(_URL_RATE_STREAM);
    es.onmessage = function (ev) {
      try { applyRateStats(JSON.parse(ev.data)); } catch (e) {}
    };
    es.onerror = function () {
      es.close();
      setTimeout(openRateStream, 5000);
    };
  }());
}());

document.addEventListener('DOMContentLoaded', function () {
  var clearBtn = document.getElementById('clear-done-btn');
  if (clearBtn) clearBtn.addEventListener('click', clearDone);

  document.querySelectorAll('.cancel-btn[data-task-id]').forEach(function (btn) {
    btn.addEventListener('click', function () { cancelTask(this.dataset.taskId, this); });
  });
});
