from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class Route:
    id: str
    subdomain: str
    upstream: str
    enabled: bool = True
    description: str = ""
    extra_directives: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GlobalSettings:
    acme_email: str = ""
    dns_provider: str = "cloudflare"
    dns_token_env: str = "CF_API_TOKEN"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CertInfo:
    domain: str
    issuer: str = ""
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    days_remaining: Optional[int] = None
    status: str = "missing"  # ok, warning, expired, missing

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReloadResult:
    ok: bool
    message: str = ""
    error_detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
