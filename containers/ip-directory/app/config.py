import os


def _env(name, default=""):
    return os.environ.get(name, default).strip()


class Config:
    def __init__(self):
        self.config_path = _env("CONFIG_PATH", "/config")
        self.port = int(_env("PORT", "9595"))
        self.refresh_minutes = int(_env("REFRESH_MINUTES", "15"))
        # How far back the very first scan of the sFlow data reaches.
        self.initial_scan_days = int(_env("INITIAL_SCAN_DAYS", "7"))

        self.influx_url = _env("INFLUX_URL", "http://192.168.1.30:8186")
        self.influx_token = _env("INFLUX_TOKEN")
        self.influx_org = _env("INFLUX_ORG", "LCARS")
        self.influx_bucket = _env("INFLUX_BUCKET", "unraid")
        self.netflow_measurement = _env("NETFLOW_MEASUREMENT", "netflow")
        self.labels_measurement = _env("LABELS_MEASUREMENT", "ip_labels")

        self.tautulli_url = _env("TAUTULLI_URL").rstrip("/")
        self.tautulli_api_key = _env("TAUTULLI_API_KEY")

        self.adguard_url = _env("ADGUARD_URL").rstrip("/")
        self.adguard_user = _env("ADGUARD_USER")
        self.adguard_password = _env("ADGUARD_PASSWORD")

        self.maxmind_account_id = _env("MAXMIND_ACCOUNT_ID")
        self.maxmind_license_key = _env("MAXMIND_LICENSE_KEY")

        # Comma-separated CIDRs treated as "your LAN" (named by MAC).
        # Hostnames the UI may be reached by (IP addresses and localhost always work), e.g. a Tailscale name.
        self.allowed_hosts = [h.strip().lower() for h in _env("ALLOWED_HOSTS").split(",") if h.strip()]
        self.lan_cidrs = [c.strip() for c in _env("LAN_CIDRS", "192.168.0.0/16,10.0.0.0/8,172.16.0.0/12").split(",") if c.strip()]

    @property
    def influx_configured(self):
        return bool(self.influx_url and self.influx_token)

    @property
    def tautulli_configured(self):
        return bool(self.tautulli_url and self.tautulli_api_key)

    @property
    def adguard_configured(self):
        return bool(self.adguard_url)

    @property
    def maxmind_configured(self):
        return bool(self.maxmind_account_id and self.maxmind_license_key)
