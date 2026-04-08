"""Access-control decorators for Flask routes.

These are pure Flask/session decorators — no database dependency needed.
They check ``flask.session`` state to determine access.
"""

from functools import wraps
from flask import abort, redirect, request, session, url_for


def require_login(fn):
    """Redirect unauthenticated users to the login page."""
    @wraps(fn)
    def _inner(*args, **kwargs):
        if "owner_id" not in session:
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)
    return _inner


def require_admin(fn):
    """Return 403 for non-admin users."""
    @wraps(fn)
    def _inner(*args, **kwargs):
        if not session.get("is_admin"):
            abort(403)
        return fn(*args, **kwargs)
    return _inner


def require_role(role: str):
    """Require an authenticated session with the named role (or admin privilege).

    - site_owner / site_admin bypass the role check entirely.
    - Users must hold *role* in their session roles to proceed.
    - Page requests (Accept: text/html) are redirected to login when unauthenticated;
      API/SSE requests receive HTTP 401.
    """
    def decorator(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            if "owner_id" not in session:
                if "text/html" in request.headers.get("Accept", ""):
                    return redirect(url_for("auth.login"))
                abort(401)
            # site_admin and site_owner bypass named-role checks
            if session.get("is_admin"):
                return fn(*args, **kwargs)
            # Lazy-load roles from DB for sessions predating this system
            if "roles" not in session:
                from core.auth.identity import get_user_roles
                session["roles"] = get_user_roles(session["owner_id"])
            if not role or role in session.get("roles", []):
                return fn(*args, **kwargs)
            abort(403)
        return _inner
    return decorator
