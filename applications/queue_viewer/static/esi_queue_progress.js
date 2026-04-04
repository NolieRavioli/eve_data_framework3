(function () {
  var _taskApp = document.getElementById('task-app');
  var TASK_ID = _taskApp.dataset.taskId;
  var _URL_STREAM = _taskApp.dataset.urlStream;
  var _URL_CANCEL = _taskApp.dataset.urlCancel;
  var consoleEl = document.getElementById('console');
  var badge = document.getElementById('status-badge');
  var cancelButton = document.getElementById('cancel-btn');

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

  var es = new EventSource(_URL_STREAM);
  es.onmessage = function (event) {
    appendLine(event.data);
  };
  function renderBuckets(groups) {
    var card = document.getElementById('esi-buckets-card');
    var list = document.getElementById('esi-buckets-list');
    var keys = Object.keys(groups).sort();
    var anyVisible = false;
    // Keep existing rows and update them; append new ones.
    var rendered = {};
    keys.forEach(function (name) {
      var g = groups[name];
      var limit = g.tokens_limit || 0;
      // Skip groups that have never had a real ESI response (remaining == null means
      // only pre-seeded; tokens_used also null → no real activity yet).
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
        '<span class="bucket-name" title="' + name + '">' + name + '</span>' +
        '<div class="bucket-bar-wrap"><div class="' + barCls + '" style="width:' + pct.toFixed(1) + '%"></div></div>' +
        '<span class="bucket-tokens">' + remaining.toLocaleString() + '\u202f/\u202f' + limit.toLocaleString() + '</span>';
    });
    // Remove rows for groups no longer present.
    Array.prototype.slice.call(list.children).forEach(function (el) {
      var name = el.title || el.querySelector('.bucket-name').title;
      if (!rendered[name]) el.remove();
    });
    card.style.display = anyVisible ? '' : 'none';
  }

  es.addEventListener('esi_rate', function (event) {
    var s = JSON.parse(event.data);
    var groups = s.groups || {};
    // Compute aggregate totals across all active groups (mirrors queue list logic).
    var totalLimit = 0, totalRemaining = 0, totalUsed = 0, worstWindow = 0;
    Object.keys(groups).forEach(function (gname) {
      var g = groups[gname];
      var limit = g.tokens_limit || 0;
      // Groups with null remaining have never had a real response — skip them
      // for the summary bar so we only show real observed data.
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
  });
  es.addEventListener('esi_requests', function (event) {
    var entries = JSON.parse(event.data);
    var log = document.getElementById('esi-req-log');
    var card = document.getElementById('esi-req-card');
    card.style.display = '';
    var atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 5;
    entries.forEach(function (e) {
      var sCls = e.status >= 500 ? 's5' : e.status >= 400 ? 's4' : e.status >= 300 ? 's3' : 's2';
      var path = e.url.replace(/^https?:\/\/[^\/]+/, '');

      // Build header rows (only if any headers were captured).
      var hdrHtml = '';
      var hdrs = e.hdrs || {};
      var hdrKeys = Object.keys(hdrs).sort();
      if (hdrKeys.length) {
        hdrHtml = hdrKeys.map(function (k) {
          return '<div class="esi-req-hdr-kv"><span class="esi-req-hdr-k">' + k + '</span><span class="esi-req-hdr-v">' + hdrs[k] + '</span></div>';
        }).join('');
      }

      var entry = document.createElement('div');
      entry.innerHTML =
        '<div class="esi-req-row">' +
          '<span class="esi-req-toggle">\u25b6</span>' +
          '<span class="esi-req-ts">' + e.ts + '</span>' +
          '<span class="esi-req-method">' + e.method + '</span>' +
          '<span class="esi-req-status ' + sCls + '">' + e.status + '</span>' +
          '<span class="esi-req-ms">' + e.ms.toLocaleString() + 'ms</span>' +
          '<span class="esi-req-url" title="' + e.url + '">' + path + '</span>' +
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
      // Cap at 300 entries (oldest dropped from top).
      if (log.children.length > 300) log.removeChild(log.firstChild);
    });
    if (atBottom) log.scrollTop = log.scrollHeight;
  });

  es.addEventListener('done', function (event) {
    setStatus(event.data);
    es.close();
  });
  es.onerror = function () {
    appendLine('[Connection lost. Reload to reconnect.]');
    es.close();
  };

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
