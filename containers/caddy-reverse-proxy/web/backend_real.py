"""Production backend.

- routes.json under /etc/caddy/ is the source of truth
- the Caddyfile is rendered from routes.json on every change
- `caddy validate` is run before writing; `caddy reload` applies it
- certs are read from /data/caddy/certificates/**/*.crt
- logs are tailed from /var/log/caddy/caddy.log (configured by the
  rendered Caddyfile's global log block)
"""

import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from caddyfile_parser import parse_caddyfile
from caddyfile_render import MARKER, render
from models import CertInfo, GlobalSettings, ReloadResult, Route

ROUTES_PATH = Path(os.environ.get("CADDY_ROUTES_PATH", "/etc/caddy/routes.json"))
CADDYFILE_PATH = Path(os.environ.get("CADDYFILE_PATH", "/etc/caddy/Caddyfile"))
CADDY_LOG_PATH = Path(os.environ.get("CADDY_LOG_PATH", "/var/log/caddy/caddy.log"))
CERTS_DIR = Path(os.environ.get("CADDY_CERTS_DIR", "/data/caddy/certificates"))
ADMIN_ADDR = os.environ.get("CADDY_ADMIN_ADDR", "127.0.0.1:2019")


class RealBackend:
    def __init__(
        self,
        routes_path: Path = ROUTES_PATH,
        caddyfile_path: Path = CADDYFILE_PATH,
        log_path: Path = CADDY_LOG_PATH,
        certs_dir: Path = CERTS_DIR,
    ):
        self.routes_path = Path(routes_path)
        self.caddyfile_path = Path(caddyfile_path)
        self.log_path = Path(log_path)
        self.certs_dir = Path(certs_dir)
        self._ensure_routes_file()

    # --- persistence ---
    def _ensure_routes_file(self) -> None:
        if self.routes_path.exists():
            return
        self.routes_path.parent.mkdir(parents=True, exist_ok=True)
        self._save(
            {
                "global": GlobalSettings().to_dict(),
                "routes": [],
                "managed": True,
                "imported": False,
            }
        )

    def _load(self) -> dict:
        return json.loads(self.routes_path.read_text())

    def _save(self, data: dict) -> None:
        tmp = self.routes_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.routes_path)

    # --- routes ---
    def list_routes(self) -> list[Route]:
        return [Route(**r) for r in self._load()["routes"]]

    def get_route(self, route_id: str) -> Optional[Route]:
        return next((r for r in self.list_routes() if r.id == route_id), None)

    def upsert_route(self, route: Route) -> None:
        if not route.id:
            route.id = str(uuid.uuid4())
        data = self._load()
        for i, r in enumerate(data["routes"]):
            if r["id"] == route.id:
                data["routes"][i] = route.to_dict()
                self._save(data)
                return
        data["routes"].append(route.to_dict())
        self._save(data)

    def delete_route(self, route_id: str) -> None:
        data = self._load()
        data["routes"] = [r for r in data["routes"] if r["id"] != route_id]
        self._save(data)

    # --- global ---
    def get_global(self) -> GlobalSettings:
        return GlobalSettings(**self._load()["global"])

    def update_global(self, g: GlobalSettings) -> None:
        data = self._load()
        data["global"] = g.to_dict()
        self._save(data)

    # --- certs ---
    def list_certs(self) -> list[CertInfo]:
        out: list[CertInfo] = []
        seen: set[str] = set()
        if self.certs_dir.exists():
            for crt_path in self.certs_dir.rglob("*.crt"):
                try:
                    info = self._parse_cert(crt_path)
                except Exception:
                    continue
                if info is None:
                    continue
                out.append(info)
                seen.add(info.domain)
        for r in self.list_routes():
            if r.enabled and r.subdomain not in seen:
                out.append(CertInfo(domain=r.subdomain, status="missing"))
        return out

    def _parse_cert(self, path: Path) -> Optional[CertInfo]:
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        cert = x509.load_pem_x509_certificate(path.read_bytes())
        try:
            cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        except IndexError:
            cn = path.stem
        try:
            issuer = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value
        except IndexError:
            issuer = ""
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
        now = datetime.now(timezone.utc)
        days = (not_after - now).days
        if days < 0:
            status = "expired"
        elif days < 7:
            status = "expired"
        elif days < 30:
            status = "warning"
        else:
            status = "ok"
        return CertInfo(
            domain=cn,
            issuer=issuer,
            not_before=not_before.isoformat(),
            not_after=not_after.isoformat(),
            days_remaining=days,
            status=status,
        )

    # --- caddyfile / reload ---
    def render_caddyfile(self) -> str:
        return render(self.get_global(), self.list_routes())

    def _write_caddyfile(self, content: str) -> None:
        self.caddyfile_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caddyfile_path.with_suffix(".tmp")
        tmp.write_text(content)
        tmp.replace(self.caddyfile_path)

    def validate(self) -> ReloadResult:
        content = self.render_caddyfile()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".Caddyfile", delete=False
        ) as f:
            f.write(content)
            tmp_path = f.name
        try:
            r = subprocess.run(
                ["caddy", "validate", "--config", tmp_path, "--adapter", "caddyfile"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode != 0:
                detail = (r.stderr or r.stdout or "").strip()
                return ReloadResult(False, "Validation failed", detail)
            return ReloadResult(True, "Config valid")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def reload(self) -> ReloadResult:
        v = self.validate()
        if not v.ok:
            return v
        self._write_caddyfile(self.render_caddyfile())
        r = subprocess.run(
            [
                "caddy",
                "reload",
                "--config",
                str(self.caddyfile_path),
                "--adapter",
                "caddyfile",
                "--address",
                ADMIN_ADDR,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r.returncode != 0:
            detail = (r.stderr or r.stdout or "").strip()
            return ReloadResult(False, "Reload failed", detail)
        return ReloadResult(True, "Reloaded successfully")

    def tail_logs(self, n: int = 200) -> list[str]:
        if not self.log_path.exists():
            return ["(no logs available yet — Caddy hasn't written to the log file)"]
        try:
            with self.log_path.open("rb") as f:
                f.seek(0, 2)
                size = f.tell()
                read = min(size, 128 * 1024)
                f.seek(size - read)
                content = f.read().decode("utf-8", errors="replace")
            return content.splitlines()[-n:]
        except OSError as e:
            return [f"(error reading logs: {e})"]

    # --- meta ---
    def is_managed(self) -> bool:
        return bool(self._load().get("managed", True))

    def has_imported(self) -> bool:
        return bool(self._load().get("imported", False))

    def import_existing(self) -> int:
        if not self.caddyfile_path.exists():
            data = self._load()
            data["imported"] = True
            self._save(data)
            return 0
        content = self.caddyfile_path.read_text()
        if MARKER in content:
            data = self._load()
            data["imported"] = True
            self._save(data)
            return 0
        try:
            g, parsed_routes = parse_caddyfile(content)
        except Exception:
            data = self._load()
            data["imported"] = True
            self._save(data)
            return 0

        data = self._load()
        if g.acme_email:
            data["global"]["acme_email"] = g.acme_email
        if g.dns_provider:
            data["global"]["dns_provider"] = g.dns_provider
        if g.dns_token_env:
            data["global"]["dns_token_env"] = g.dns_token_env

        existing = {r["subdomain"] for r in data["routes"]}
        added = 0
        for r in parsed_routes:
            if r.subdomain in existing:
                continue
            data["routes"].append(r.to_dict())
            added += 1
        data["imported"] = True
        self._save(data)
        return added

    def reset(self) -> None:
        # not exposed for the real backend (would wipe user data)
        raise RuntimeError("reset is only supported in mock mode")

    def check_upstream(self, upstream: str) -> dict:
        import socket

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
        try:
            with socket.create_connection((host, port_n), timeout=2.0):
                return {"ok": True, "message": "reachable"}
        except socket.timeout:
            return {"ok": False, "message": "timeout (2s)"}
        except socket.gaierror:
            return {"ok": False, "message": "DNS lookup failed"}
        except OSError as e:
            return {"ok": False, "message": f"unreachable: {e.strerror or e}"}
