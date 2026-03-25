"""Flask routes for the backup web GUI."""

import time
from datetime import datetime, timezone
from glob import glob
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for

from backup.common import _format_interval
from backup.state import shared_state
from backup.sources import ALL_SOURCES
from . import config_manager

bp = Blueprint(
    "main", __name__,
    static_folder="static",
    static_url_path="/static",
    template_folder="templates",
)


def _handler_for_type(source_type):
    for handler in ALL_SOURCES:
        if handler.SOURCE_TYPE == source_type:
            return handler
    return None


def _list_backup_files(source_name):
    """Scan the filesystem for backup files belonging to a source."""
    files = []
    for handler in ALL_SOURCES:
        source_dir = handler.backup_dir(source_name)
        if not source_dir.exists():
            continue
        for ext in ("*.sql.gz", "*.tar.gz", "*.json.gz"):
            pattern = str(source_dir / "**" / ext)
            for filepath in glob(pattern, recursive=True):
                p = Path(filepath)
                stat = p.stat()
                files.append({
                    "name": p.name,
                    "path": str(p),
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                })
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return files


def _extract_form_data(source_type, form):
    """Build a source dict from the HTML form data."""
    data = {"name": form.get("name", "").strip()}

    if source_type == "mysql":
        data["host"] = form.get("host", "").strip()
        port_str = form.get("port", "3306").strip()
        data["port"] = int(port_str) if port_str.isdigit() else 3306
        data["user"] = form.get("user", "").strip()
        data["password"] = form.get("password", "")
        databases = form.get("databases", "").strip()
        data["databases"] = [d.strip() for d in databases.split(",") if d.strip()]
    elif source_type == "azure":
        data["account_name"] = form.get("account_name", "").strip()
        data["account_key"] = form.get("account_key", "").strip()
        blobs = form.get("blobs", "").strip()
        data["blobs"] = [b.strip() for b in blobs.split(",") if b.strip()]
        files = form.get("files", "").strip()
        data["files"] = [f.strip() for f in files.split(",") if f.strip()]
        tables = form.get("tables", "").strip()
        data["tables"] = [t.strip() for t in tables.split(",") if t.strip()]

    interval = form.get("backup_interval", "").strip()
    if interval:
        data["backup_interval"] = interval
    retention = form.get("backup_retention", "").strip()
    if retention:
        data["backup_retention"] = retention

    return data


def _validate_source(source_type, data):
    """Validate source data using the existing handler validators.

    Returns a list of error strings (empty if valid).
    """
    handler = _handler_for_type(source_type)
    if handler is None:
        return [f"Unknown source type: {source_type}"]
    errors = []
    # Use a copy so validation mutations don't leak into the original
    test_data = dict(data)
    handler.validate(test_data, 0, errors, 86400, 30)
    return errors


@bp.route("/")
def dashboard():
    try:
        config = config_manager.read_raw_config()
    except (FileNotFoundError, ValueError):
        config = {}

    all_sources = []
    for handler in ALL_SOURCES:
        for source in config.get(handler.CONFIG_KEY, []):
            all_sources.append({
                "name": source.get("name", "?"),
                "type": handler.SOURCE_TYPE,
                "interval": source.get("backup_interval", ""),
                "retention": source.get("backup_retention", ""),
            })

    statuses = shared_state.get_all_sources()

    # Merge scheduler status into source list
    for src in all_sources:
        status = statuses.get(src["name"])
        if status:
            src["is_running"] = status.is_running
            src["last_error"] = status.last_error
            src["last_backup_wall"] = status.last_backup_wall
            src["interval_seconds"] = status.interval_seconds
            src["retention_count"] = status.retention_count
        else:
            src["is_running"] = False
            src["last_error"] = None
            src["last_backup_wall"] = None
            src["interval_seconds"] = 0
            src["retention_count"] = 0

    # Compute display values
    now_ts = time.time()
    for src in all_sources:
        # Format interval/retention from scheduler if available, else from config string
        if src["interval_seconds"]:
            src["interval_display"] = _format_interval(int(src["interval_seconds"]))
        else:
            src["interval_display"] = src["interval"] or "default"

        if src["retention_count"]:
            src["retention_display"] = f"{src['retention_count']} copies"
        else:
            src["retention_display"] = src["retention"] or "default"

        # Last backup time
        wall = src["last_backup_wall"]
        if wall:
            age = now_ts - wall
            src["last_backup_display"] = _format_age(age)
            # Next due
            if src["interval_seconds"]:
                next_in = src["interval_seconds"] - age
                src["next_due_display"] = _format_age(max(0, next_in)) if next_in > 0 else "now"
            else:
                src["next_due_display"] = "—"
        else:
            src["last_backup_display"] = "never"
            src["next_due_display"] = "soon"

        # Status label
        if src["is_running"]:
            src["status"] = "running"
        elif src["last_error"]:
            src["status"] = "error"
        else:
            src["status"] = "idle"

    return render_template("dashboard.html", sources=all_sources)


def _format_age(seconds):
    """Format a duration in seconds to a human-readable string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


@bp.route("/source/<name>")
def source_detail(name):
    try:
        config = config_manager.read_raw_config()
    except (FileNotFoundError, ValueError):
        flash("Could not read config file.", "error")
        return redirect(url_for("main.dashboard"))

    source, source_type = config_manager.get_source_by_name(config, name)
    if source is None:
        flash(f"Source '{name}' not found.", "error")
        return redirect(url_for("main.dashboard"))

    status = shared_state.get_source(name)
    backup_files = _list_backup_files(name)

    return render_template(
        "source_detail.html",
        source=source,
        source_type=source_type,
        status=status,
        backup_files=backup_files,
    )


@bp.route("/source/<name>/backup", methods=["POST"])
def trigger_backup(name):
    shared_state.request_manual_backup(name)
    flash(f"Manual backup requested for '{name}'.", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/source/add/<source_type>", methods=["GET", "POST"])
def add_source(source_type):
    handler = _handler_for_type(source_type)
    if handler is None:
        flash(f"Unknown source type: {source_type}", "error")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        data = _extract_form_data(source_type, request.form)

        # Check duplicate name
        try:
            config = config_manager.read_raw_config()
        except (FileNotFoundError, ValueError):
            config = {}

        existing, _ = config_manager.get_source_by_name(config, data.get("name", ""))
        if existing:
            flash(f"A source named '{data['name']}' already exists.", "error")
            return render_template("source_form.html", source_type=source_type, source=data, editing=False)

        errors = _validate_source(source_type, data)
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("source_form.html", source_type=source_type, source=data, editing=False)

        config_manager.add_source(config, source_type, data)
        config_manager.write_config(config)
        flash(f"Source '{data['name']}' added successfully.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("source_form.html", source_type=source_type, source={}, editing=False)


@bp.route("/source/<name>/edit", methods=["GET", "POST"])
def edit_source(name):
    try:
        config = config_manager.read_raw_config()
    except (FileNotFoundError, ValueError):
        flash("Could not read config file.", "error")
        return redirect(url_for("main.dashboard"))

    source, source_type = config_manager.get_source_by_name(config, name)
    if source is None:
        flash(f"Source '{name}' not found.", "error")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        data = _extract_form_data(source_type, request.form)

        # If name changed, check for duplicates
        if data["name"] != name:
            existing, _ = config_manager.get_source_by_name(config, data["name"])
            if existing:
                flash(f"A source named '{data['name']}' already exists.", "error")
                return render_template("source_form.html", source_type=source_type, source=data, editing=True, original_name=name)

        errors = _validate_source(source_type, data)
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("source_form.html", source_type=source_type, source=data, editing=True, original_name=name)

        config_manager.update_source(config, name, source_type, data)
        config_manager.write_config(config)
        flash(f"Source '{data['name']}' updated successfully.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("source_form.html", source_type=source_type, source=source, editing=True, original_name=name)


@bp.route("/source/<name>/delete", methods=["GET", "POST"])
def delete_source(name):
    try:
        config = config_manager.read_raw_config()
    except (FileNotFoundError, ValueError):
        flash("Could not read config file.", "error")
        return redirect(url_for("main.dashboard"))

    source, source_type = config_manager.get_source_by_name(config, name)
    if source is None:
        flash(f"Source '{name}' not found.", "error")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        config_manager.delete_source(config, name)
        config_manager.write_config(config)
        flash(f"Source '{name}' deleted.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("confirm_delete.html", source=source, source_type=source_type)
