# core/web/home.py
"""Public home page blueprint — served at / for unauthenticated visitors."""

from flask import Blueprint, render_template

from core.web.context import base_ctx

home_bp = Blueprint("home", __name__, template_folder="templates")


@home_bp.route("/", strict_slashes=False)
def index():
    return render_template("home.html", **base_ctx("home"))
