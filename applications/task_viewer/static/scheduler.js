/* applications/scheduler/static/scheduler.js */

(function () {
  "use strict";

  /* ── Index page ──────────────────────────────────────────────────────── */

  var indexApp = document.getElementById('scheduler-app');
  if (indexApp) {
    var _URL_TOGGLE   = indexApp.dataset.urlToggle;
    var _URL_RUN_NOW  = indexApp.dataset.urlRunNow;
    var _URL_PROGRESS = indexApp.dataset.urlProgress;
    var _CSRF_TOKEN   = indexApp.dataset.csrf;

    function toggleJob(btn) {
      var jobId = btn.dataset.job;
      fetch(_URL_TOGGLE.replace('PLACEHOLDER', encodeURIComponent(jobId)), {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': _CSRF_TOKEN },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.error) { alert(data.error); return; }
          var enabled = data.enabled;
          btn.dataset.enabled = enabled ? 'true' : 'false';
          btn.textContent = enabled ? 'Disable' : 'Enable';
          var badge = document.getElementById('badge-' + jobId);
          if (badge) {
            badge.textContent = enabled ? 'Enabled' : 'Disabled';
            badge.className = 'badge ' + (enabled ? 'badge-on' : 'badge-off');
          }
        })
        .catch(function () { alert('Request failed'); });
    }

    function runNow(btn) {
      var jobId = btn.dataset.job;
      btn.disabled = true;
      btn.textContent = 'Queued…';
      fetch(_URL_RUN_NOW.replace('PLACEHOLDER', encodeURIComponent(jobId)), {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': _CSRF_TOKEN },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.error) { alert(data.error); btn.disabled = false; btn.textContent = 'Run Now'; return; }
          if (data.task_id) {
            window.location.href = _URL_PROGRESS.replace('PLACEHOLDER', data.task_id);
          } else {
            btn.disabled = false;
            btn.textContent = 'Run Now';
          }
        })
        .catch(function () { btn.disabled = false; btn.textContent = 'Run Now'; });
    }

    document.querySelectorAll('.js-toggle-btn').forEach(function (btn) {
      btn.addEventListener('click', function () { toggleJob(this); });
    });
    document.querySelectorAll('.js-run-btn').forEach(function (btn) {
      btn.addEventListener('click', function () { runNow(this); });
    });
  }

  /* ── Detail page ─────────────────────────────────────────────────────── */

  var detailApp = document.getElementById('scheduler-detail-app');
  if (detailApp) {
    var toggleUrl   = detailApp.dataset.urlToggle;
    var runNowUrl   = detailApp.dataset.urlRunNow;
    var intervalUrl = detailApp.dataset.urlInterval;
    var progressUrl = detailApp.dataset.urlProgress;
    var csrfToken   = detailApp.dataset.csrf;

    var btnToggle  = document.getElementById('btn-toggle');
    var btnRunNow  = document.getElementById('btn-run-now');
    var intervalForm = document.getElementById('interval-form');

    if (btnToggle) {
      btnToggle.addEventListener('click', function () {
        fetch(toggleUrl, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': csrfToken },
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.error) { alert(data.error); return; }
            var enabled = data.enabled;
            btnToggle.dataset.enabled = enabled ? 'true' : 'false';
            btnToggle.textContent = enabled ? 'Disable' : 'Enable';
            var badge = document.getElementById('badge-status');
            if (badge) {
              badge.textContent = enabled ? 'Enabled' : 'Disabled';
              badge.className = 'badge ' + (enabled ? 'badge-on' : 'badge-off');
            }
          })
          .catch(function () { alert('Request failed'); });
      });
    }

    if (btnRunNow) {
      btnRunNow.addEventListener('click', function () {
        btnRunNow.disabled = true;
        btnRunNow.textContent = 'Queued…';
        fetch(runNowUrl, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': csrfToken },
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.error) { alert(data.error); btnRunNow.disabled = false; btnRunNow.textContent = 'Run Now'; return; }
            if (data.task_id) {
              window.location.href = progressUrl.replace('PLACEHOLDER', data.task_id);
            } else {
              btnRunNow.disabled = false;
              btnRunNow.textContent = 'Run Now';
            }
          })
          .catch(function () { btnRunNow.disabled = false; btnRunNow.textContent = 'Run Now'; });
      });
    }

    if (intervalForm) {
      intervalForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = intervalForm.querySelector('input[name="interval_s"]');
        var val = parseInt(input.value, 10);
        if (isNaN(val) || val < 60) { alert('Interval must be at least 60 seconds'); return; }
        var fd = new FormData();
        fd.append('interval_s', val);
        fetch(intervalUrl, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': csrfToken },
          body: fd,
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.error) { alert(data.error); return; }
            var display = document.getElementById('display-interval');
            if (display) display.textContent = data.interval_seconds + 's';
          })
          .catch(function () { alert('Request failed'); });
      });
    }
  }

}());
