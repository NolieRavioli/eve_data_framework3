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

  var es = new EventSource('/tasks/' + TASK_ID + '/stream');
  es.onmessage = function (event) {
    appendLine(event.data);
  };
  es.addEventListener('esi_rate', function (event) {
    var s = JSON.parse(event.data);
    var pct = s.tokens_limit > 0 ? (s.tokens_used / s.tokens_limit * 100) : 0;
    var bar = document.getElementById('esi-rate-bar');
    bar.style.width = pct.toFixed(1) + '%';
    bar.className = 'esi-rate-bar' + (pct >= 90 ? ' danger' : pct >= 70 ? ' warn' : '');
    document.getElementById('esi-tokens-used').textContent = s.tokens_used.toLocaleString();
    document.getElementById('esi-tokens-limit').textContent = s.tokens_limit.toLocaleString();
    document.getElementById('esi-tokens-remaining').textContent = s.tokens_remaining.toLocaleString();
    document.getElementById('esi-window').textContent = s.window_seconds;
    document.getElementById('esi-requests-total').textContent = s.requests_total.toLocaleString();
    document.getElementById('esi-rate-card').style.display = '';
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
    fetch('/tasks/' + TASK_ID + '/cancel', { method: 'POST' })
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        if (payload.cancelled) setStatus('cancelled');
        else if (payload.message) appendLine('[INFO] ' + payload.message);
      });
  };
}());
