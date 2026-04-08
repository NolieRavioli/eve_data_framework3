(function () {
  var _taskApp = document.getElementById('task-app');
  var TASK_ID = _taskApp.dataset.taskId;
  var _URL_WS = _taskApp.dataset.urlWs;
  var _URL_CANCEL = _taskApp.dataset.urlCancel;
  var consoleEl = document.getElementById('console');
  var badge = document.getElementById('status-badge');
  var cancelButton = document.getElementById('cancel-btn');

  function escHtml(s) {
    if (!s) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function appendLine(text) {
    var span = document.createElement('span');
    span.className = 'ln';
    if (text.indexOf('[ERROR]') >= 0 || text.indexOf('[FAIL') >= 0) span.classList.add('err');
    else if (text.indexOf('[OK]') >= 0 || text.indexOf('[DONE]') >= 0 || text.indexOf('[CANCELLED]') >= 0) span.classList.add('ok');
    else if (text.indexOf('[START]') >= 0) span.classList.add('head');
    span.textContent = text;
    consoleEl.appendChild(span);
    consoleEl.scrollTop = consoleEl.scrollHeight;
  }

  function setStatus(status) {
    badge.textContent = status;
    badge.className = 'task-status ' + status;
    if (cancelButton && status !== 'pending') {
      cancelButton.remove();
      cancelButton = null;
    }
  }

  function renderBuckets(groups) {
    var card = document.getElementById('esi-buckets-card');
    var list = document.getElementById('esi-buckets-list');
    var keys = Object.keys(groups).sort();
    var anyVisible = false;
    var rendered = {};
    keys.forEach(function (name) {
      var g = groups[name];
      var limit = g.tokens_limit || 0;
      if (g.tokens_remaining == null && !g.tokens_used) return;
      anyVisible = true;
      rendered[name] = true;
      var remaining = g.tokens_remaining != null ? g.tokens_remaining : limit;
      var used = limit > 0 ? Math.max(0, limit - remaining) : (g.tokens_used || 0);
      var pct = limit > 0 ? (used / limit * 100) : 0;
      var barCls = pct >= 90 ? 'bucket-bar danger' : pct >= 70 ? 'bucket-bar warn' : 'bucket-bar';
      var elId = 'bkt-' + name.replace(/[^a-z0-9]/gi, '_');
      var row = document.getElementById(elId);
      if (!row) {
        row = document.createElement('div');
        row.id = elId;
        row.className = 'bucket-row';
        list.appendChild(row);
      }
      row.innerHTML =
        '<span class="bucket-name" title="' + escHtml(name) + '">' + escHtml(name) + '</span>' +
        '<div class="bucket-bar-wrap"><div class="' + barCls + '" style="width:' + pct.toFixed(1) + '%"></div></div>' +
        '<span class="bucket-tokens">' + remaining.toLocaleString() + '\u202f/\u202f' + limit.toLocaleString() + '</span>';
    });
    Array.prototype.slice.call(list.children).forEach(function (el) {
      var name = el.querySelector('.bucket-name').title;
      if (!rendered[name]) el.remove();
    });
    card.style.display = anyVisible ? '' : 'none';
  }

  function applyEsiRate(s) {
    var groups = s.groups || {};
    var totalLimit = 0, totalRemaining = 0, totalUsed = 0, worstWindow = 0;
    Object.keys(groups).forEach(function (gname) {
      var g = groups[gname];
      var limit = g.tokens_limit || 0;
      if (g.tokens_remaining == null) return;
      var used = limit > 0 ? Math.max(0, limit - g.tokens_remaining) : (g.tokens_used || 0);
      totalLimit += limit;
      totalRemaining += g.tokens_remaining;
      totalUsed += used;
      if ((g.window_seconds || 0) > worstWindow) worstWindow = g.window_seconds;
    });
    var pct = totalLimit > 0 ? (totalUsed / totalLimit * 100) : 0;
    var bar = document.getElementById('esi-rate-bar');
    bar.style.width = pct.toFixed(1) + '%';
    bar.className = 'esi-rate-bar' + (pct >= 90 ? ' danger' : pct >= 70 ? ' warn' : '');
    document.getElementById('esi-tokens-used').textContent = totalUsed.toLocaleString();
    document.getElementById('esi-tokens-limit').textContent = totalLimit.toLocaleString();
    document.getElementById('esi-tokens-remaining').textContent = totalRemaining.toLocaleString();
    document.getElementById('esi-window').textContent = worstWindow || (s.window_seconds || '—');
    document.getElementById('esi-requests-total').textContent = (s.requests_total || 0).toLocaleString();
    document.getElementById('esi-rate-card').style.display = '';
    if (groups) renderBuckets(groups);
  }

  function applyEsiRequests(entries) {
    var log = document.getElementById('esi-req-log');
    var card = document.getElementById('esi-req-card');
    card.style.display = '';
    var atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 5;
    entries.forEach(function (e) {
      var sCls = e.status >= 500 ? 's5' : e.status >= 400 ? 's4' : e.status >= 300 ? 's3' : 's2';
      var path = e.url.replace(/^https?:\/\/[^\/]+/, '');
      var hdrs = e.hdrs || {};
      var hdrKeys = Object.keys(hdrs).sort();
      var hdrHtml = hdrKeys.length ? hdrKeys.map(function (k) {
        return '<div class="esi-req-hdr-kv"><span class="esi-req-hdr-k">' + escHtml(k) + '</span><span class="esi-req-hdr-v">' + escHtml(hdrs[k]) + '</span></div>';
      }).join('') : '';
      var entry = document.createElement('div');
      entry.innerHTML =
        '<div class="esi-req-row">' +
          '<span class="esi-req-toggle">\u25b6</span>' +
          '<span class="esi-req-ts">' + escHtml(e.ts) + '</span>' +
          '<span class="esi-req-method">' + escHtml(e.method) + '</span>' +
          '<span class="esi-req-status ' + sCls + '">' + e.status + '</span>' +
          '<span class="esi-req-ms">' + e.ms.toLocaleString() + 'ms</span>' +
          '<span class="esi-req-url" title="' + escHtml(e.url) + '">' + escHtml(path) + '</span>' +
        '</div>' +
        (hdrHtml ? '<div class="esi-req-hdrs">' + hdrHtml + '</div>' : '');
      if (hdrHtml) {
        var row = entry.querySelector('.esi-req-row');
        var hdrsEl = entry.querySelector('.esi-req-hdrs');
        var toggle = entry.querySelector('.esi-req-toggle');
        row.addEventListener('click', function () {
          var open = hdrsEl.style.display === 'block';
          hdrsEl.style.display = open ? 'none' : 'block';
          toggle.style.transform = open ? '' : 'rotate(90deg)';
        });
      }
      log.appendChild(entry);
      if (log.children.length > 300) log.removeChild(log.firstChild);
    });
    if (atBottom) log.scrollTop = log.scrollHeight;
  }

  // ── WebSocket connection to per-task endpoint ─────────────────────────────
  (function connectTaskWS() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws;
    try { ws = new WebSocket(proto + '//' + location.host + _URL_WS); }
    catch (e) {
      appendLine('[Connection error — could not open WebSocket.]');
      return;
    }

    ws.onmessage = function (event) {
      try {
        var msg = JSON.parse(event.data);

        // History replay: entries for task/<id>/log replay previous publishes.
        if (msg.type === 'history') {
          (msg.entries || []).forEach(function (e) {
            if (!e.data) return;
            dispatchTaskEvent(e.data);
          });
          return;
        }

        // Live push: {type:"publish", topic:"task/<id>/log", data:{type:...}}
        if (msg.type === 'publish' && msg.data) {
          dispatchTaskEvent(msg.data);
        }
      } catch (e) {}
    };

    ws.onclose = function () {
      appendLine('[Connection closed. Reload to reconnect.]');
    };
    ws.onerror = function () {
      appendLine('[WebSocket error.]');
      ws.close();
    };
  }());

  function dispatchTaskEvent(data) {
    var t = data.type;
    if (t === 'log') {
      appendLine(data.message || '');
    } else if (t === 'esi_rate') {
      applyEsiRate(data);
    } else if (t === 'esi_requests') {
      applyEsiRequests(data.entries || []);
    } else if (t === 'done') {
      setStatus(data.status || 'complete');
    }
  }

  window.cancelTask = function () {
    fetch(_URL_CANCEL, { method: 'POST' })
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        if (payload.cancelled) setStatus('cancelled');
        else if (payload.message) appendLine('[INFO] ' + payload.message);
      });
  };

  if (cancelButton) cancelButton.addEventListener('click', window.cancelTask);
}());
