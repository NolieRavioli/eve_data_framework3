/* applications/scheduler/static/scheduler.js */

function toggleJob(btn) {
  const jobId = btn.dataset.job;
  const currentlyEnabled = btn.dataset.enabled === 'true';

  fetch(`/admin/scheduler/${jobId}/toggle`, {
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

  fetch(`/admin/scheduler/${jobId}/run-now`, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  })
    .then(r => r.json())
    .then(data => {
      if (data.error) { alert(data.error); btn.disabled = false; btn.textContent = 'Run Now'; return; }
      if (data.task_id) {
        window.location.href = '/queue?' + new URLSearchParams({ task_id: data.task_id });
      } else {
        btn.disabled = false;
        btn.textContent = 'Run Now';
      }
    })
    .catch(() => { btn.disabled = false; btn.textContent = 'Run Now'; });
}
