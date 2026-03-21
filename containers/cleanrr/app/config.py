import os


class Config:
    def __init__(self):
        self.deluge_host = os.environ.get("DELUGE_HOST", "localhost")
        self.deluge_port = int(os.environ.get("DELUGE_PORT", "8112"))
        self.deluge_password = os.environ.get("DELUGE_PASSWORD", "deluge")
        self.config_path = os.environ.get("CONFIG_PATH", "/config")
