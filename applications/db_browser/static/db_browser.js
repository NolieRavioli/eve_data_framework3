var activeTableEl = null;
var BROWSER_OWNER_ID = document.getElementById('db-app').dataset.ownerId || null;

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
        var r = await fetch('/admin/db_browser/query', {
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
