(function () {
  var TASK_ID = document.getElementById('task-app').dataset.taskId;
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

  var es = new EventSource('/queue/' + TASK_ID + '/stream');
  es.onmessage = function (event) {
    appendLine(event.data);
  };
  function renderBuckets(groups) {
    var card = document.getElementById('esi-buckets-card');
    var list = document.getElementById('esi-buckets-list');
    var keys = Object.keys(groups).sort();
    if (!keys.length) { card.style.display = 'none'; return; }
    list.innerHTML = '';
    keys.forEach(function (name) {
      var g = groups[name];
      var limit = g.tokens_limit || 0;
      var remaining = g.tokens_remaining != null ? g.tokens_remaining : limit;
      var used = limit > 0 ? Math.max(0, limit - remaining) : (g.tokens_used || 0);
      var pct = limit > 0 ? (used / limit * 100) : 0;
      var barCls = pct >= 90 ? 'bucket-bar danger' : pct >= 70 ? 'bucket-bar warn' : 'bucket-bar';
      var row = document.createElement('div');
      row.className = 'bucket-row';
      row.innerHTML =
        '<span class="bucket-name" title="' + name + '">' + name + '</span>' +
        '<div class="bucket-bar-wrap"><div class="' + barCls + '" style="width:' + pct.toFixed(1) + '%"></div></div>' +
        '<span class="bucket-tokens">' + remaining.toLocaleString() + '\u202f/\u202f' + limit.toLocaleString() + '</span>';
      list.appendChild(row);
    });
    card.style.display = '';
  }

  es.addEventListener('esi_rate', function (event) {
    var s = JSON.parse(event.data);
    var effectiveUsed = s.tokens_limit > 0
                        ? Math.max(0, s.tokens_limit - (s.tokens_remaining || 0))
                        : (s.tokens_used || 0);
    var pct = s.tokens_limit > 0 ? (effectiveUsed / s.tokens_limit * 100) : 0;
    var bar = document.getElementById('esi-rate-bar');
    bar.style.width = pct.toFixed(1) + '%';
    bar.className = 'esi-rate-bar' + (pct >= 90 ? ' danger' : pct >= 70 ? ' warn' : '');
    document.getElementById('esi-tokens-used').textContent = effectiveUsed.toLocaleString();
    document.getElementById('esi-tokens-limit').textContent = s.tokens_limit.toLocaleString();
    document.getElementById('esi-tokens-remaining').textContent = s.tokens_remaining.toLocaleString();
    document.getElementById('esi-window').textContent = s.window_seconds;
    document.getElementById('esi-requests-total').textContent = s.requests_total.toLocaleString();
    document.getElementById('esi-rate-card').style.display = '';
    if (s.groups) renderBuckets(s.groups);
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
    fetch('/queue/' + TASK_ID + '/cancel', { method: 'POST' })
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        if (payload.cancelled) setStatus('cancelled');
        else if (payload.message) appendLine('[INFO] ' + payload.message);
      });
  };
}());
