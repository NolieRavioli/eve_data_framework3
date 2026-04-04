/* applications/scheduler/static/scheduler.js */

var _schedApp   = document.getElementById('scheduler-app');
var _URL_TOGGLE   = _schedApp.dataset.urlToggle;
var _URL_RUN_NOW  = _schedApp.dataset.urlRunNow;
var _URL_PROGRESS = _schedApp.dataset.urlProgress;

function toggleJob(btn) {
  const jobId = btn.dataset.job;
  const currentlyEnabled = btn.dataset.enabled === 'true';

  fetch(_URL_TOGGLE.replace('PLACEHOLDER', encodeURIComponent(jobId)), {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  })
    .then(r => r.json())
    .then(data => {
      if (data.error) { alert(data.error); return; }
      const enabled = data.enabled;
      btn.dataset.enabled = enabled ? 'true' : 'false';
      btn.textContent = enabled ? 'Disable' : 'Enable';
      const badge = document.getElementById('badge-' + jobId);
      if (badge) {
        badge.textContent = enabled ? 'Enabled' : 'Disabled';
        badge.className = 'badge ' + (enabled ? 'badge-on' : 'badge-off');
      }
    })
    .catch(() => alert('Request failed'));
}

function runNow(btn) {
  const jobId = btn.dataset.job;
  btn.disabled = true;
  btn.textContent = 'Queued…';

  fetch(_URL_RUN_NOW.replace('PLACEHOLDER', encodeURIComponent(jobId)), {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  })
    .then(r => r.json())
    .then(data => {
      if (data.error) { alert(data.error); btn.disabled = false; btn.textContent = 'Run Now'; return; }
      if (data.task_id) {
        window.location.href = _URL_PROGRESS.replace('PLACEHOLDER', data.task_id);
      } else {
        btn.disabled = false;
        btn.textContent = 'Run Now';
      }
    })
    .catch(() => { btn.disabled = false; btn.textContent = 'Run Now'; });
}

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.js-toggle-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { toggleJob(this); });
  });
  document.querySelectorAll('.js-run-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { runNow(this); });
  });
});
