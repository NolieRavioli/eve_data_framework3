/**
 * Admin — user detail page: role management, admin toggle, delete.
 */
(function () {
  'use strict';

  var app = document.getElementById('user-detail-app');
  if (!app) return;

  var _URL_ROLES  = app.dataset.urlRoles;
  var _URL_ADMIN  = app.dataset.urlAdmin;
  var _URL_DELETE = app.dataset.urlDelete;
  var _URL_USERS  = app.dataset.urlUsers;

  function showMsg(message, isErr) {
    var bar = document.getElementById('msg-bar');
    bar.textContent = message;
    bar.className = 'admin-msg ' + (isErr ? 'err' : 'ok');
    window.setTimeout(function () { bar.className = 'admin-msg'; }, 3500);
  }

  // ── Roles ──────────────────────────────────────────────────────────────

  function grantRole() {
    var input = document.getElementById('new-role-input');
    var role = input.value.trim();
    if (!role) return;

    fetch(_URL_ROLES, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'grant', role: role }),
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.ok) { showMsg('Role "' + role + '" granted.', false); location.reload(); }
      else showMsg(d.error || 'Failed', true);
    })
    .catch(function (e) { showMsg(e.toString(), true); });
  }

  function revokeRole(role) {
    fetch(_URL_ROLES, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'revoke', role: role }),
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.ok) { showMsg('Role "' + role + '" revoked.', false); location.reload(); }
      else showMsg(d.error || 'Failed', true);
    })
    .catch(function (e) { showMsg(e.toString(), true); });
  }

  // ── Admin toggle ───────────────────────────────────────────────────────

  function toggleAdmin(action) {
    if (action === 'demote' && !window.confirm('Demote this user from admin?')) return;

    fetch(_URL_ADMIN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action }),
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.ok) { showMsg(action === 'promote' ? 'Promoted.' : 'Demoted.', false); location.reload(); }
      else showMsg(d.error || 'Failed', true);
    })
    .catch(function (e) { showMsg(e.toString(), true); });
  }

  // ── Delete ─────────────────────────────────────────────────────────────

  function deleteUser() {
    if (!window.confirm('Permanently delete this user? This cannot be undone.')) return;

    fetch(_URL_DELETE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.ok) { window.location.href = _URL_USERS; }
      else showMsg(d.error || 'Delete failed', true);
    })
    .catch(function (e) { showMsg(e.toString(), true); });
  }

  // ── Bind events ────────────────────────────────────────────────────────

  var grantBtn = document.getElementById('grant-role-btn');
  if (grantBtn) grantBtn.addEventListener('click', grantRole);

  var roleInput = document.getElementById('new-role-input');
  if (roleInput) roleInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') grantRole();
  });

  document.querySelectorAll('.role-remove-btn').forEach(function (btn) {
    btn.addEventListener('click', function () { revokeRole(this.dataset.role); });
  });

  var promoteBtn = document.getElementById('promote-btn');
  if (promoteBtn) promoteBtn.addEventListener('click', function () { toggleAdmin('promote'); });

  var demoteBtn = document.getElementById('demote-btn');
  if (demoteBtn) demoteBtn.addEventListener('click', function () { toggleAdmin('demote'); });

  var deleteBtn = document.getElementById('delete-user-btn');
  if (deleteBtn) deleteBtn.addEventListener('click', deleteUser);
}());
