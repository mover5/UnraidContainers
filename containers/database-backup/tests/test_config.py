"""Tests for backup.config — load_config validation."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from backup.config import load_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path, data):
    cfg = tmp_path / "servers.json"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    return str(cfg)


_MINIMAL_MYSQL = {
    "mysql_servers": [
        {
            "name": "db1",
            "host": "localhost",
            "user": "root",
            "password": "secret",
            "databases": ["mydb"],
        }
    ]
}

_MINIMAL_AZURE = {
    "storage_accounts": [
        {
            "name": "acct1",
            "account_name": "myaccount",
            "account_key": "key==",
            "blobs": ["container1"],
        }
    ]
}


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestLoadConfigValid:
    def test_minimal_mysql_config(self, tmp_path):
        cfg_path = _write_config(tmp_path, _MINIMAL_MYSQL)
        config = load_config(cfg_path)
        assert "mysql_servers" in config
        assert config["mysql_servers"][0]["name"] == "db1"

    def test_defaults_applied(self, tmp_path):
        cfg_path = _write_config(tmp_path, _MINIMAL_MYSQL)
        config = load_config(cfg_path)
        # Default interval 24h = 86400s, retention 30d
        assert config["interval"] == 86400
        assert config["retention"] == 30 * 86400

    def test_global_interval_override(self, tmp_path):
        data = dict(_MINIMAL_MYSQL)
        data["backup_interval"] = "6h"
        data["backup_retention"] = "7d"
        cfg_path = _write_config(tmp_path, data)
        config = load_config(cfg_path)
        assert config["interval"] == 6 * 3600
        assert config["retention"] == 7 * 86400

    def test_per_source_interval_override(self, tmp_path):
        data = {
            "mysql_servers": [
                {
                    "name": "db1",
                    "host": "localhost",
                    "user": "root",
                    "password": "secret",
                    "databases": ["mydb"],
                    "backup_interval": "30m",
                    "backup_retention": "3d",
                }
            ]
        }
        cfg_path = _write_config(tmp_path, data)
        config = load_config(cfg_path)
        src = config["mysql_servers"][0]
        assert src["_interval"] == 30 * 60
        assert src["_retention"] == 3 * 86400

    def test_source_inherits_global_interval(self, tmp_path):
        data = dict(_MINIMAL_MYSQL)
        data["backup_interval"] = "2h"
        cfg_path = _write_config(tmp_path, data)
        config = load_config(cfg_path)
        assert config["mysql_servers"][0]["_interval"] == 2 * 3600

    def test_mysql_default_port_set(self, tmp_path):
        cfg_path = _write_config(tmp_path, _MINIMAL_MYSQL)
        config = load_config(cfg_path)
        assert config["mysql_servers"][0]["port"] == 3306

    def test_legacy_servers_key_accepted(self, tmp_path):
        data = {
            "servers": [
                {
                    "name": "db1",
                    "host": "localhost",
                    "user": "root",
                    "password": "secret",
                    "databases": ["mydb"],
                }
            ]
        }
        cfg_path = _write_config(tmp_path, data)
        config = load_config(cfg_path)
        assert len(config["mysql_servers"]) == 1

    def test_minimal_azure_config(self, tmp_path):
        cfg_path = _write_config(tmp_path, _MINIMAL_AZURE)
        config = load_config(cfg_path)
        assert config["storage_accounts"][0]["name"] == "acct1"

    def test_azure_defaults_applied(self, tmp_path):
        cfg_path = _write_config(tmp_path, _MINIMAL_AZURE)
        config = load_config(cfg_path)
        src = config["storage_accounts"][0]
        assert src.get("files") == []
        assert src.get("tables") == []


# ---------------------------------------------------------------------------
# Error / exit tests
# ---------------------------------------------------------------------------

class TestLoadConfigErrors:
    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_config(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_exits(self, tmp_path):
        bad = tmp_path / "servers.json"
        bad.write_text("{ not json }", encoding="utf-8")
        with pytest.raises(SystemExit):
            load_config(str(bad))

    def test_no_sources_exits(self, tmp_path):
        cfg_path = _write_config(tmp_path, {"backup_interval": "6h"})
        with pytest.raises(SystemExit):
            load_config(cfg_path)

    def test_mysql_missing_required_field_exits(self, tmp_path):
        data = {
            "mysql_servers": [
                {"name": "db1", "host": "localhost", "user": "root", "databases": ["mydb"]}
                # missing 'password'
            ]
        }
        cfg_path = _write_config(tmp_path, data)
        with pytest.raises(SystemExit):
            load_config(cfg_path)

    def test_mysql_empty_databases_exits(self, tmp_path):
        data = {
            "mysql_servers": [
                {
                    "name": "db1",
                    "host": "localhost",
                    "user": "root",
                    "password": "secret",
                    "databases": [],
                }
            ]
        }
        cfg_path = _write_config(tmp_path, data)
        with pytest.raises(SystemExit):
            load_config(cfg_path)

    def test_invalid_global_interval_exits(self, tmp_path):
        data = dict(_MINIMAL_MYSQL)
        data["backup_interval"] = "bad"
        cfg_path = _write_config(tmp_path, data)
        with pytest.raises(SystemExit):
            load_config(cfg_path)

    def test_invalid_per_source_interval_exits(self, tmp_path):
        data = {
            "mysql_servers": [
                {
                    "name": "db1",
                    "host": "localhost",
                    "user": "root",
                    "password": "secret",
                    "databases": ["mydb"],
                    "backup_interval": "bad",
                }
            ]
        }
        cfg_path = _write_config(tmp_path, data)
        with pytest.raises(SystemExit):
            load_config(cfg_path)

    def test_azure_missing_account_key_exits(self, tmp_path):
        data = {
            "storage_accounts": [
                {
                    "name": "acct1",
                    "account_name": "myaccount",
                    # missing account_key
                    "blobs": ["container1"],
                }
            ]
        }
        cfg_path = _write_config(tmp_path, data)
        with pytest.raises(SystemExit):
            load_config(cfg_path)

    def test_azure_no_resources_exits(self, tmp_path):
        data = {
            "storage_accounts": [
                {
                    "name": "acct1",
                    "account_name": "myaccount",
                    "account_key": "key==",
                    # blobs/files/tables all empty / absent
                }
            ]
        }
        cfg_path = _write_config(tmp_path, data)
        with pytest.raises(SystemExit):
            load_config(cfg_path)
