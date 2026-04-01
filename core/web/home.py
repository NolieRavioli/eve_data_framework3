# core/web/home.py
"""Public home page blueprint — served at / for unauthenticated visitors."""

from flask import Blueprint, redirect, render_template, session, url_for

from core.web.context import base_ctx

home_bp = Blueprint("home", __name__, template_folder="templates")


@home_bp.route("/", strict_slashes=False)
def index():
    if session.get("owner_id"):
        return redirect(url_for("dashboard.home"))
    return render_template("home.html", **base_ctx("home"))
