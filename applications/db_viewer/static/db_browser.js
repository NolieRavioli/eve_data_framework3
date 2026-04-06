var activeTableEl = null;
var _dbApp = document.getElementById('db-app');
var BROWSER_OWNER_ID = _dbApp.dataset.ownerId || null;
var _URL_QUERY = _dbApp.dataset.urlQuery;

function selectTable(name, el) {
    var cols = document.getElementById('cols-' + name);
    if (activeTableEl && activeTableEl !== el) {
        var prev = activeTableEl.nextElementSibling;
        if (prev) prev.classList.remove('visible');
        activeTableEl.classList.remove('active');
    }
    activeTableEl = el;
    el.classList.toggle('active');
    cols.classList.toggle('visible');
    document.getElementById('sql-input').value = 'SELECT * FROM "' + name + '" LIMIT 100;';
}

function clearQuery() {
    document.getElementById('sql-input').value = '';
    document.getElementById('results-head').innerHTML = '';
    document.getElementById('results-body').innerHTML = '';
    document.getElementById('row-count').textContent = '';
    setStatus('', '');
}

function setStatus(msg, cls) {
    var el = document.getElementById('query-status');
    el.textContent = msg;
    el.className = cls;
}

async function runQuery() {
    var sql = document.getElementById('sql-input').value.trim();
    if (!sql) return;
    setStatus('Running…', '');
    try {
        var r = await fetch(_URL_QUERY, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({sql: sql, owner_id: BROWSER_OWNER_ID}),
        });
        var j = await r.json();
        if (j.error) { setStatus('Error: ' + j.error, 'err'); return; }

        var head = document.getElementById('results-head');
        var body = document.getElementById('results-body');
        head.innerHTML = '<tr>' + j.columns.map(function(c) { return '<th>' + c + '</th>'; }).join('') + '</tr>';
        body.innerHTML = j.rows.map(function(row) {
            return '<tr>' + j.columns.map(function(c) {
                var v = row[c];
                if (v === null || v === undefined) v = '<span style="opacity:0.35">NULL</span>';
                else if (typeof v === 'object') v = JSON.stringify(v);
                return '<td>' + v + '</td>';
            }).join('') + '</tr>';
        }).join('');

        var cnt = j.rows.length;
        document.getElementById('row-count').textContent = cnt + ' row' + (cnt !== 1 ? 's' : '') + ' returned' + (cnt === 500 ? ' (limit reached)' : '');
        setStatus('OK — ' + cnt + ' rows', 'ok');
    } catch (e) {
        setStatus('Fetch error: ' + e.message, 'err');
    }
}

document.getElementById('sql-input').addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') runQuery();
});

var autoTimer = null;

function toggleAuto() {
    if (autoTimer) {
        clearInterval(autoTimer);
        autoTimer = null;
        var btn = document.getElementById('auto-btn');
        btn.textContent = '\u21BB Auto';
        btn.classList.remove('btn-a');
        btn.classList.add('btn-g');
        setStatus('Auto-refresh stopped', '');
    } else {
        var sql = document.getElementById('sql-input').value.trim();
        if (!sql) { setStatus('Enter a query first', 'err'); return; }
        var interval = parseInt(document.getElementById('auto-interval').value, 10) * 1000;
        var btn = document.getElementById('auto-btn');
        btn.textContent = '\u25A0 Stop';
        btn.classList.remove('btn-g');
        btn.classList.add('btn-a');
        runQuery();
        autoTimer = setInterval(function() {
            var currentSql = document.getElementById('sql-input').value.trim();
            if (!currentSql) { toggleAuto(); return; }
            runQuery();
        }, interval);
    }
}

document.addEventListener('DOMContentLoaded', function () {
  var runBtn = document.getElementById('run-query-btn');
  if (runBtn) runBtn.addEventListener('click', runQuery);

  var clearBtn = document.getElementById('clear-query-btn');
  if (clearBtn) clearBtn.addEventListener('click', clearQuery);

  var autoBtn = document.getElementById('auto-btn');
  if (autoBtn) autoBtn.addEventListener('click', toggleAuto);

  document.querySelectorAll('.table-item[data-tname]').forEach(function (el) {
    el.addEventListener('click', function () { selectTable(this.dataset.tname, this); });
  });
});
