var consoleEl = document.getElementById('console-output');
var statusDot = document.getElementById('status-dot');
var sseStatus = document.getElementById('sse-status');
var autoScroll = true;
var _adminApp = document.getElementById('admin-app');
var _URL_STREAM  = _adminApp.dataset.urlStream;
var _URL_PROMOTE = _adminApp.dataset.urlPromote;
var _URL_DEMOTE  = _adminApp.dataset.urlDemote;

function appendLine(text) {
  var line = document.createElement('span');
  line.className = 'log-line';
  if (text.indexOf('[ERROR]') >= 0 || text.indexOf('ERROR') >= 0) line.classList.add('ERROR');
  else if (text.indexOf('[WARNING]') >= 0 || text.indexOf('WARNING') >= 0) line.classList.add('WARNING');
  else if (text.indexOf('[INFO]') >= 0 || text.indexOf('INFO') >= 0) line.classList.add('INFO');
  else line.classList.add('DEBUG');
  line.textContent = text;
  consoleEl.appendChild(line);
  if (autoScroll) consoleEl.scrollTop = consoleEl.scrollHeight;
  while (consoleEl.children.length > 600) consoleEl.removeChild(consoleEl.firstChild);
}

function clearConsole() {
  consoleEl.innerHTML = '';
}

function toggleScroll() {
  autoScroll = !autoScroll;
  document.getElementById('scroll-label').textContent = autoScroll ? 'ON' : 'OFF';
}

function showMsg(message, isErr) {
  var bar = document.getElementById('msg-bar');
  bar.textContent = message;
  bar.className = 'admin-msg ' + (isErr ? 'err' : 'ok');
  window.setTimeout(function () { bar.className = 'admin-msg'; }, 3500);
}

function filterUsers(value) {
  var needle = value.trim().toLowerCase();
  var rows = document.querySelectorAll('#user-table tbody tr');
  rows.forEach(function (row) {
    var owner = (row.getAttribute('data-owner') || '').toLowerCase();
    var role = (row.getAttribute('data-role') || '').toLowerCase();
    row.style.display = !needle || owner.indexOf(needle) >= 0 || role.indexOf(needle) >= 0 ? '' : 'none';
  });
}

(function connectSSE() {
  var es = new EventSource(_URL_STREAM);
  es.onopen = function () {
    statusDot.className = 'status-dot';
    sseStatus.textContent = 'Connected';
  };
  es.onmessage = function (event) {
    try { appendLine(JSON.parse(event.data)); }
    catch (err) { appendLine(event.data); }
  };
  es.onerror = function () {
    statusDot.className = 'status-dot offline';
    sseStatus.textContent = 'Disconnected';
  };
}());

async function promote(ownerId) {
  var response = await fetch(_URL_PROMOTE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ owner_id: ownerId })
  });
  var payload = await response.json();
  if (payload.ok) {
    showMsg('Owner ' + ownerId + ' promoted.', false);
    window.setTimeout(function () { location.reload(); }, 400);
  } else {
    showMsg(payload.error || 'Promote failed.', true);
  }
}

async function demote(ownerId) {
  if (!window.confirm('Demote owner ' + ownerId + '?')) return;
  var response = await fetch(_URL_DEMOTE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ owner_id: ownerId })
  });
  var payload = await response.json();
  if (payload.ok) {
    showMsg('Owner ' + ownerId + ' demoted.', false);
    window.setTimeout(function () { location.reload(); }, 400);
  } else {
    showMsg(payload.error || 'Demote failed.', true);
  }
}

document.addEventListener('DOMContentLoaded', function () {
  var toggleScrollBtn = document.getElementById('toggle-scroll-btn');
  if (toggleScrollBtn) toggleScrollBtn.addEventListener('click', toggleScroll);

  var clearConsoleBtn = document.getElementById('clear-console-btn');
  if (clearConsoleBtn) clearConsoleBtn.addEventListener('click', clearConsole);

  var userFilter = document.getElementById('user-filter');
  if (userFilter) userFilter.addEventListener('input', function () { filterUsers(this.value); });

  document.querySelectorAll('.js-demote-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { demote(parseInt(this.dataset.owner, 10)); });
  });
  document.querySelectorAll('.js-promote-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { promote(parseInt(this.dataset.owner, 10)); });
  });
});
