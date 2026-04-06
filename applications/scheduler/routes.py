# applications/scheduler/routes.py
"""Scheduler admin blueprint."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from applications._api import base_ctx, require_admin
from applications._api import scheduler

logger = logging.getLogger(__name__)
scheduler_bp = Blueprint(
    "scheduler", __name__, template_folder="templates", static_folder="static"
)


@scheduler_bp.route("/")
@require_admin
def index():
    jobs = scheduler.list_jobs()
    return render_template("scheduler.html", jobs=jobs, **base_ctx("scheduler"))


@scheduler_bp.route("/<job_id>")
@require_admin
def detail(job_id: str):
    job = scheduler.get_job(job_id)
    if job is None:
        return redirect(url_for("scheduler.index"))
    history = scheduler.get_run_history(job_id, limit=25)
    return render_template(
        "scheduler_detail.html",
        job=job,
        history=history,
        **base_ctx("scheduler"),
    )


@scheduler_bp.route("/<job_id>/toggle", methods=["POST"])
@require_admin
def toggle(job_id: str):
    jobs = {j["job_id"]: j for j in scheduler.list_jobs()}
    if job_id not in jobs:
        return jsonify({"error": "unknown job"}), 404
    new_state = not jobs[job_id]["enabled"]
    scheduler.set_enabled(job_id, new_state)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"job_id": job_id, "enabled": new_state})
    return redirect(url_for("scheduler.index"))


@scheduler_bp.route("/<job_id>/run-now", methods=["POST"])
@require_admin
def run_now(job_id: str):
    jobs = {j["job_id"]: j for j in scheduler.list_jobs()}
    if job_id not in jobs:
        return jsonify({"error": "unknown job"}), 404
    task_id = scheduler.run_now(job_id)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"task_id": task_id})
    return redirect(url_for("esi_viewer.task_detail", task_id=task_id))


@scheduler_bp.route("/<job_id>/interval", methods=["POST"])
@require_admin
def change_interval(job_id: str):
    job = scheduler.get_job(job_id)
    if job is None:
        return jsonify({"error": "unknown job"}), 404
    try:
        new_interval = int(request.form["interval_s"])
    except (KeyError, ValueError):
        return jsonify({"error": "invalid interval"}), 400
    if new_interval < 60:
        return jsonify({"error": "Interval must be at least 60 seconds"}), 400
    scheduler.set_interval(job_id, new_interval)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"job_id": job_id, "interval_seconds": new_interval})
    return redirect(url_for("scheduler.detail", job_id=job_id))
