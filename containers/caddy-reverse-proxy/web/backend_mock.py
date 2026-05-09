"""In-memory backend backed by a fixtures JSON file.

Used for local dev/iteration without Docker, Caddy, or Cloudflare.
Validation deliberately fails on bogus ports so the error UX is reachable.
"""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from caddyfile_render import render
from models import CertInfo, GlobalSettings, ReloadResult, Route


FIXTURES = Path(__file__).parent / "fixtures" / "mock_data.json"


class MockBackend:
    def __init__(self, fixtures_path: Path = FIXTURES):
        self.fixtures_path = fixtures_path
        self.reset()

    def reset(self) -> None:
        data = json.loads(self.fixtures_path.read_text())
        self._global = GlobalSettings(**data["global"])
        self._routes: list[Route] = [Route(**r) for r in data["routes"]]
        self._cert_specs: list[dict] = data.get("certs", [])
        self._logs: list[str] = data.get("logs", [])
        self._managed = True
        self._imported = True

    # --- routes ---
    def list_routes(self) -> list[Route]:
        return list(self._routes)

    def get_route(self, route_id: str) -> Optional[Route]:
        return next((r for r in self._routes if r.id == route_id), None)

    def upsert_route(self, route: Route) -> None:
        if not route.id:
            route.id = str(uuid.uuid4())
        for i, r in enumerate(self._routes):
            if r.id == route.id:
                self._routes[i] = route
                return
        self._routes.append(route)

    def delete_route(self, route_id: str) -> None:
        self._routes = [r for r in self._routes if r.id != route_id]

    # --- global ---
    def get_global(self) -> GlobalSettings:
        return self._global

    def update_global(self, g: GlobalSettings) -> None:
        self._global = g

    # --- certs ---
    def list_certs(self) -> list[CertInfo]:
        out: list[CertInfo] = []
        seen: set[str] = set()
        now = datetime.now(timezone.utc)
        for spec in self._cert_specs:
            domain = spec["domain"]
            seen.add(domain)
            status = spec.get("status", "ok")
            if status == "missing":
                out.append(CertInfo(domain=domain, status="missing"))
                continue
            days = spec.get("not_after_days", 60)
            not_after = now + timedelta(days=days)
            not_before = not_after - timedelta(days=90)
            out.append(
                CertInfo(
                    domain=domain,
                    issuer=spec.get("issuer", "Let's Encrypt"),
                    not_before=not_before.isoformat(),
                    not_after=not_after.isoformat(),
                    days_remaining=days,
                    status=status,
                )
            )
        for r in self._routes:
            if r.enabled and r.subdomain not in seen:
                out.append(CertInfo(domain=r.subdomain, status="missing"))
        return out

    # --- caddyfile / reload ---
    def render_caddyfile(self) -> str:
        return render(self._global, self._routes)

    def validate(self) -> ReloadResult:
        for r in self._routes:
            if not r.enabled:
                continue
            if ":" not in r.upstream:
                return ReloadResult(
                    False,
                    "Validation failed",
                    f"upstream for {r.subdomain!r} is missing a port: {r.upstream!r}",
                )
            host, _, port = r.upstream.rpartition(":")
            if not host:
                return ReloadResult(
                    False, "Validation failed", f"upstream for {r.subdomain!r} has no host"
                )
            try:
                p = int(port)
            except ValueError:
                return ReloadResult(
                    False,
                    "Validation failed",
                    f"non-numeric port for {r.subdomain!r}: {port!r}",
                )
            if p < 1 or p > 65535:
                return ReloadResult(
                    False,
                    "Validation failed",
                    f"port out of range for {r.subdomain!r}: {p}",
                )
            if "." not in r.subdomain:
                return ReloadResult(
                    False,
                    "Validation failed",
                    f"subdomain must contain a dot: {r.subdomain!r}",
                )
        return ReloadResult(True, "Config valid")

    def reload(self) -> ReloadResult:
        v = self.validate()
        if not v.ok:
            return v
        time.sleep(0.2)  # simulate reload latency
        ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S.000")
        self._logs.append(f"{ts}\tINFO\tadmin\tconfig reloaded via UI")
        return ReloadResult(True, "Reloaded successfully")

    def tail_logs(self, n: int = 200) -> list[str]:
        return self._logs[-n:]

    # --- meta ---
    def is_managed(self) -> bool:
        return self._managed

    def has_imported(self) -> bool:
        return self._imported

    def import_existing(self) -> int:
        return 0  # mock fixtures already populated

    def check_upstream(self, upstream: str) -> dict:
        upstream = upstream.strip()
        if not upstream:
            return {"ok": False, "message": "empty"}
        if ":" not in upstream:
            return {"ok": False, "message": "missing port"}
        host, _, port = upstream.rpartition(":")
        if not host:
            return {"ok": False, "message": "missing host"}
        try:
            port_n = int(port)
        except ValueError:
            return {"ok": False, "message": "non-numeric port"}
        if port_n < 1 or port_n > 65535:
            return {"ok": False, "message": "port out of range"}
        # simulate a small connect delay so the pending state is visible
        time.sleep(0.25)
        # any upstream that's already in the fixtures is reachable
        if any(r.upstream == upstream for r in self._routes):
            return {"ok": True, "message": "reachable (mock)"}
        # forced-failure patterns so the red state is testable
        if "down" in host.lower() or "fail" in host.lower():
            return {"ok": False, "message": "connection refused (mock)"}
        if port_n == 9999:
            return {"ok": False, "message": "connection refused (mock)"}
        return {"ok": True, "message": "reachable (mock)"}
