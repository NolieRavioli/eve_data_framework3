# core/web/setup.py
"""Setup wizard blueprint — guides new installs through credential configuration."""

import os

from flask import Blueprint, redirect, render_template, request, url_for

from core.auth.credentials import CredentialManager

setup_bp = Blueprint("setup", __name__, template_folder="templates")


def _credentials_exist() -> bool:
    public_data = os.getenv("PUBLIC_DATA_FOLDER", "_publicData")
    return os.path.exists(os.path.join(public_data, "client_cred"))


@setup_bp.route("/setup", methods=["GET"])
def index():
    if _credentials_exist():
        return redirect(url_for("home.index"))
    try:
        from core.esi.generated.manifest import ALL_SCOPES
        all_scopes = sorted(ALL_SCOPES)
    except Exception:
        all_scopes = []
    return render_template("setup.html", step=1, all_scopes=all_scopes, error=None)


@setup_bp.route("/setup", methods=["POST"])
def save():
    client_id = request.form.get("client_id", "").strip()
    client_secret = request.form.get("client_secret", "").strip()
    redirect_uri = request.form.get("redirect_uri", "").strip()
    raw_scopes = request.form.get("scopes", "").strip()

    try:
        from core.esi.generated.manifest import ALL_SCOPES
        all_scopes = sorted(ALL_SCOPES)
    except Exception:
        all_scopes = []

    if not (client_id and client_secret and redirect_uri):
        return render_template(
            "setup.html", step=1, all_scopes=all_scopes,
            error="Client ID, Client Secret, and Callback URL are all required.",
        )

    # Normalise scopes: accept JSON array, or newline/comma/space separated
    import re, json
    raw_scopes_stripped = raw_scopes.strip()
    if raw_scopes_stripped.startswith("["):
        try:
            parsed = json.loads(raw_scopes_stripped)
            scopes_list = [s.strip() for s in parsed if isinstance(s, str) and s.strip()]
        except (json.JSONDecodeError, TypeError):
            scopes_list = []
    else:
        scopes_list = [s.strip() for s in re.split(r"[\s,]+", raw_scopes_stripped) if s.strip()]
    scopes_str = " ".join(scopes_list) if scopes_list else " ".join(all_scopes)

    CredentialManager.save_credentials(client_id, client_secret, redirect_uri, scopes_str)
    return redirect(url_for("setup.owner"))


@setup_bp.route("/setup/owner")
def owner():
    return render_template("setup.html", step=2, all_scopes=[], error=None)
