"""Caddy reverse-proxy admin UI.

Listens on port 9999. Talks to a Backend (real or mock) for everything
that touches Caddy or the filesystem — see backend.py.
"""

import os
import secrets

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from backend import backend_mode, get_backend
from models import GlobalSettings, Route


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(16))

backend = get_backend()


@app.context_processor
def inject_globals():
    return {
        "mode": backend_mode(),
        "managed": backend.is_managed(),
    }


@app.route("/")
def index():
    return redirect(url_for("routes_list"))


# ---------- routes ----------

@app.route("/routes")
def routes_list():
    show_import_banner = backend_mode() == "real" and not backend.has_imported()
    return render_template(
        "routes.html",
        active="routes",
        routes=backend.list_routes(),
        show_import_banner=show_import_banner,
    )


@app.route("/routes/new", methods=["GET", "POST"])
def routes_new():
    if request.method == "POST":
        route = _route_from_form(request.form, route_id="")
        sub_check = backend.check_subdomain(route.subdomain)
        if not sub_check["ok"]:
            flash(f"Subdomain {route.subdomain!r} {sub_check['message']}", "error")
            return render_template(
                "route_form.html",
                active="routes",
                route=route,
                form_action=url_for("routes_new"),
                form_title="New route",
            )
        backend.upsert_route(route)
        result = backend.reload()
        if not result.ok:
            backend.delete_route(route.id)
            flash(f"{result.message}: {result.error_detail}", "error")
            return render_template(
                "route_form.html",
                active="routes",
                route=route,
                form_action=url_for("routes_new"),
                form_title="New route",
            )
        flash(f"Added {route.subdomain}", "success")
        return redirect(url_for("routes_list"))
    return render_template(
        "route_form.html",
        active="routes",
        route=Route(id="", subdomain="", upstream="", enabled=True),
        form_action=url_for("routes_new"),
        form_title="New route",
    )


@app.route("/routes/<route_id>/edit", methods=["GET", "POST"])
def routes_edit(route_id):
    existing = backend.get_route(route_id)
    if not existing:
        abort(404)
    if request.method == "POST":
        route = _route_from_form(request.form, route_id=route_id)
        sub_check = backend.check_subdomain(route.subdomain, route_id=route_id)
        if not sub_check["ok"]:
            flash(f"Subdomain {route.subdomain!r} {sub_check['message']}", "error")
            return render_template(
                "route_form.html",
                active="routes",
                route=route,
                form_action=url_for("routes_edit", route_id=route_id),
                form_title=f"Edit {existing.subdomain}",
            )
        backend.upsert_route(route)
        result = backend.reload()
        if not result.ok:
            backend.upsert_route(existing)  # roll back
            flash(f"{result.message}: {result.error_detail}", "error")
            return render_template(
                "route_form.html",
                active="routes",
                route=route,
                form_action=url_for("routes_edit", route_id=route_id),
                form_title=f"Edit {existing.subdomain}",
            )
        flash(f"Updated {route.subdomain}", "success")
        return redirect(url_for("routes_list"))
    return render_template(
        "route_form.html",
        active="routes",
        route=existing,
        form_action=url_for("routes_edit", route_id=route_id),
        form_title=f"Edit {existing.subdomain}",
    )


@app.route("/routes/<route_id>/delete", methods=["POST"])
def routes_delete(route_id):
    existing = backend.get_route(route_id)
    if not existing:
        abort(404)
    backend.delete_route(route_id)
    result = backend.reload()
    if not result.ok:
        backend.upsert_route(existing)
        flash(f"{result.message}: {result.error_detail}", "error")
    else:
        flash(f"Deleted {existing.subdomain}", "success")
    return redirect(url_for("routes_list"))


@app.route("/routes/<route_id>/toggle", methods=["POST"])
def routes_toggle(route_id):
    existing = backend.get_route(route_id)
    if not existing:
        abort(404)
    existing.enabled = not existing.enabled
    backend.upsert_route(existing)
    result = backend.reload()
    if not result.ok:
        existing.enabled = not existing.enabled
        backend.upsert_route(existing)
        flash(f"{result.message}: {result.error_detail}", "error")
    else:
        state = "enabled" if existing.enabled else "disabled"
        flash(f"{existing.subdomain} {state}", "success")
    return redirect(url_for("routes_list"))


def _route_from_form(form, route_id: str) -> Route:
    return Route(
        id=route_id,
        subdomain=form.get("subdomain", "").strip().lower(),
        upstream=form.get("upstream", "").strip(),
        enabled=form.get("enabled") == "on",
        description=form.get("description", "").strip(),
        extra_directives=form.get("extra_directives", "").strip(),
    )


# ---------- certs ----------

@app.route("/certs")
def certs():
    return render_template(
        "certs.html",
        active="certs",
        certs=backend.list_certs(),
    )


# ---------- settings ----------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        old = backend.get_global()
        new = GlobalSettings(
            acme_email=request.form.get("acme_email", "").strip(),
            dns_provider=request.form.get("dns_provider", "cloudflare").strip() or "cloudflare",
            dns_token_env=request.form.get("dns_token_env", "CF_API_TOKEN").strip() or "CF_API_TOKEN",
        )
        backend.update_global(new)
        result = backend.reload()
        if not result.ok:
            backend.update_global(old)
            flash(f"{result.message}: {result.error_detail}", "error")
        else:
            flash("Settings saved", "success")
        return redirect(url_for("settings"))
    return render_template(
        "settings.html",
        active="settings",
        g=backend.get_global(),
    )


# ---------- caddyfile preview ----------

@app.route("/caddyfile")
def caddyfile():
    return render_template(
        "caddyfile.html",
        active="caddyfile",
        content=backend.render_caddyfile(),
    )


# ---------- logs ----------

@app.route("/logs")
def logs():
    n = int(request.args.get("n", 200))
    return render_template(
        "logs.html",
        active="logs",
        lines=backend.tail_logs(n),
        n=n,
    )


# ---------- api ----------

@app.route("/api/check-upstream")
def api_check_upstream():
    upstream = request.args.get("upstream", "")
    return jsonify(backend.check_upstream(upstream))


@app.route("/api/check-subdomain")
def api_check_subdomain():
    subdomain = request.args.get("subdomain", "")
    route_id = request.args.get("route_id", "")
    return jsonify(backend.check_subdomain(subdomain, route_id))


# ---------- actions ----------

@app.route("/reload", methods=["POST"])
def reload_now():
    result = backend.reload()
    if result.ok:
        flash("Reloaded successfully", "success")
    else:
        flash(f"{result.message}: {result.error_detail}", "error")
    return redirect(request.referrer or url_for("routes_list"))


@app.route("/import", methods=["POST"])
def import_existing():
    n = backend.import_existing()
    if n:
        result = backend.reload()
        if result.ok:
            flash(f"Imported {n} route(s) from existing Caddyfile", "success")
        else:
            flash(
                f"Imported {n} route(s) but reload failed: {result.error_detail}",
                "error",
            )
    else:
        flash("No routes imported (file already managed or empty)", "info")
    return redirect(url_for("routes_list"))


@app.route("/dismiss-import", methods=["POST"])
def dismiss_import():
    # mark imported without actually parsing anything
    if hasattr(backend, "_load") and hasattr(backend, "_save"):
        data = backend._load()
        data["imported"] = True
        backend._save(data)
    flash("Import banner dismissed", "info")
    return redirect(url_for("routes_list"))


@app.route("/reset", methods=["POST"])
def reset():
    if backend_mode() != "mock":
        abort(403)
    backend.reset()
    flash("Mock data reset", "info")
    return redirect(url_for("routes_list"))


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "9999"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
