/**
 * ESI Operation detail page — parameter inputs + execute.
 */
(function () {
  'use strict';

  var app = document.getElementById('esi-op-app');
  if (!app) return;

  var op;
  try { op = JSON.parse(app.dataset.op); } catch (e) { return; }

  var _URL_RUN = app.dataset.urlRun;

  // Build path parameter inputs
  var paramsDiv = document.getElementById('op-params');
  var pathParams = (op.parameters || []).filter(function (p) { return p['in'] === 'path'; });
  if (pathParams.length) {
    pathParams.forEach(function (p) {
      var wrapper = document.createElement('div');
      wrapper.innerHTML =
        '<label style="font-size:.72rem;color:var(--muted);display:block;margin-bottom:.2rem;">' +
          p.name + (p.required ? ' <span style="color:var(--bad)">*</span>' : '') +
        '</label>' +
        '<input type="text" id="param-' + p.name + '" placeholder="' + p.name + '"' +
               ' style="width:100%;background:rgba(7,18,29,.7);border:1px solid var(--border);' +
                      'border-radius:.6rem;padding:.42rem .65rem;color:var(--text-strong);' +
                      'font-family:var(--font-mono);font-size:.8rem;">';
      paramsDiv.appendChild(wrapper);
    });
  }

  function runOp() {
    var btn = document.getElementById('op-run-btn');
    btn.textContent = '\u23f3 Running\u2026';
    btn.disabled = true;

    var pathP = {};
    document.querySelectorAll('[id^="param-"]').forEach(function (el) {
      var key = el.id.replace('param-', '');
      if (el.value.trim()) pathP[key] = el.value.trim();
    });

    var queryP = {};
    var raw = document.getElementById('op-query').value;
    raw.split('\n').forEach(function (line) {
      var parts = line.split('=');
      var k = parts[0];
      var rest = parts.slice(1).join('=');
      if (k && k.trim()) queryP[k.trim()] = rest.trim();
    });

    var allPages = false;
    var apCheck = document.getElementById('op-all-pages');
    if (apCheck) allPages = apCheck.checked;

    fetch(_URL_RUN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path_params: pathP, query_params: queryP, all_pages: allPages }),
    })
    .then(function (r) { return r.json(); })
    .then(function (resp) {
      var respDiv = document.getElementById('op-response');
      var statusEl = document.getElementById('op-resp-status');
      var bodyEl = document.getElementById('op-resp-body');
      respDiv.style.display = '';

      if (resp.ok) {
        var count = resp.count !== undefined ? ' \u00b7 ' + resp.count + ' items' : '';
        var sc = resp.status_code ? ' \u00b7 HTTP ' + resp.status_code : '';
        statusEl.innerHTML = '<span style="color:var(--good);">\u2713 OK' + sc + count + '</span>';
        bodyEl.textContent = JSON.stringify(resp.data, null, 2);
      } else {
        statusEl.innerHTML = '<span style="color:var(--bad);">\u2717 Error</span>';
        bodyEl.textContent = resp.error || JSON.stringify(resp, null, 2);
      }
    })
    .catch(function (err) {
      document.getElementById('op-response').style.display = '';
      document.getElementById('op-resp-status').innerHTML = '<span style="color:var(--bad);">\u2717 Network error</span>';
      document.getElementById('op-resp-body').textContent = err.toString();
    })
    .finally(function () {
      btn.textContent = '\u25b6 Run';
      btn.disabled = false;
    });
  }

  var runBtn = document.getElementById('op-run-btn');
  if (runBtn) runBtn.addEventListener('click', runOp);
}());
