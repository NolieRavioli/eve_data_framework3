var _currentOpId = null;
var allRows = Array.from(document.querySelectorAll('.op-row'));

function filterOps(q) {
  var term = q.toLowerCase().trim();
  var method = document.getElementById('method-filter').value;
  var auth = document.getElementById('auth-filter').value;

  var visible = 0;
  for (var i = 0; i < allRows.length; i++) {
    var row = allRows[i];
    var matchText = !term || row.dataset.text.includes(term);
    var matchMethod = !method || row.dataset.method === method;
    var matchAuth = !auth || row.dataset.auth === auth;
    var show = matchText && matchMethod && matchAuth;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  }
  document.getElementById('match-count').textContent = visible + ' operations';
}

function selectOp(opId) {
  if (_currentOpId === opId) return;
  _currentOpId = opId;

  allRows.forEach(function(r) { r.classList.toggle('selected', r.dataset.id === opId); });

  fetch('/admin/esi/' + encodeURIComponent(opId))
    .then(function(r) { return r.json(); })
    .then(function(op) { populateDetail(op); });
}

function populateDetail(op) {
  var panel = document.getElementById('detail-panel');
  panel.style.display = '';

  document.getElementById('dp-tag').textContent = (op.tags || []).join(' · ');
  var methodEl = document.getElementById('dp-method');
  methodEl.textContent = op.method;
  methodEl.className = 'method-badge method-' + op.method.toLowerCase();
  document.getElementById('dp-op').textContent = op.operation_id;
  document.getElementById('dp-path').textContent = op.path;
  document.getElementById('dp-summary').textContent = op.summary || '';

  // Scopes
  var scopesWrap = document.getElementById('dp-scopes-wrap');
  var scopesDiv = document.getElementById('dp-scopes');
  var scopes = op.scopes || [];
  if (scopes.length) {
    scopesWrap.style.display = '';
    scopesDiv.innerHTML = scopes.map(function(s) { return '<span class="scope-chip">' + s + '</span>'; }).join('');
  } else {
    scopesWrap.style.display = 'none';
  }

  // Path params
  var pathParams = (op.parameters || []).filter(function(p) { return p.in === 'path'; });
  var paramsWrap = document.getElementById('dp-params-wrap');
  var paramsDiv = document.getElementById('dp-params');
  if (pathParams.length) {
    paramsWrap.style.display = '';
    paramsDiv.innerHTML = pathParams.map(function(p) {
      return '<div>' +
        '<label style="font-size:.72rem;color:var(--muted);display:block;margin-bottom:.2rem;">' +
          p.name + (p.required ? ' <span style="color:var(--bad)">*</span>' : '') +
        '</label>' +
        '<input type="text" id="param-' + p.name + '" placeholder="' + p.name + '"' +
               ' style="width:100%;background:rgba(7,18,29,.7);border:1px solid var(--border);' +
                      'border-radius:.6rem;padding:.42rem .65rem;color:var(--text-strong);' +
                      'font-family:var(--font-mono);font-size:.8rem;">' +
      '</div>';
    }).join('');
  } else {
    paramsWrap.style.display = 'none';
  }

  // Pagination toggle
  var pagesWrap = document.getElementById('dp-pages-wrap');
  pagesWrap.style.display = (op.pagination && op.pagination.has_page_param) ? '' : 'none';

  // Clear response
  document.getElementById('dp-response').style.display = 'none';
  document.getElementById('dp-query').value = '';
}

function runOp() {
  if (!_currentOpId) return;
  var btn = document.getElementById('dp-run-btn');
  btn.textContent = '⏳ Running…';
  btn.disabled = true;

  var pathParams = {};
  document.querySelectorAll('[id^="param-"]').forEach(function(el) {
    var key = el.id.replace('param-', '');
    if (el.value.trim()) pathParams[key] = el.value.trim();
  });

  var queryParams = {};
  var raw = document.getElementById('dp-query').value;
  raw.split('\n').forEach(function(line) {
    var parts = line.split('=');
    var k = parts[0];
    var rest = parts.slice(1).join('=');
    if (k && k.trim()) queryParams[k.trim()] = rest.trim();
  });

  var allPages = document.getElementById('dp-all-pages').checked;

  fetch('/admin/esi/' + encodeURIComponent(_currentOpId) + '/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({path_params: pathParams, query_params: queryParams, all_pages: allPages}),
  })
  .then(function(r) { return r.json(); })
  .then(function(resp) {
    var respDiv = document.getElementById('dp-response');
    var statusEl = document.getElementById('dp-resp-status');
    var bodyEl = document.getElementById('dp-resp-body');
    respDiv.style.display = '';

    if (resp.ok) {
      var count = resp.count !== undefined ? ' · ' + resp.count + ' items' : '';
      var sc = resp.status_code ? ' · HTTP ' + resp.status_code : '';
      statusEl.innerHTML = '<span style="color:var(--good);">✓ OK' + sc + count + '</span>';
      bodyEl.textContent = JSON.stringify(resp.data, null, 2);
    } else {
      statusEl.innerHTML = '<span style="color:var(--bad);">✗ Error</span>';
      bodyEl.textContent = resp.error || JSON.stringify(resp, null, 2);
    }
  })
  .catch(function(err) {
    document.getElementById('dp-response').style.display = '';
    document.getElementById('dp-resp-status').innerHTML = '<span style="color:var(--bad);">✗ Network error</span>';
    document.getElementById('dp-resp-body').textContent = err.toString();
  })
  .finally(function() {
    btn.textContent = '▶ Run';
    btn.disabled = false;
  });
}

// Init count
filterOps('');
