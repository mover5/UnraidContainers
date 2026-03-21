"""Tests for backup.web.config_manager — config JSON CRUD."""

import json

import pytest

from backup.web.config_manager import (
    read_raw_config,
    write_config,
    get_source_by_name,
    add_source,
    update_source,
    delete_source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(tmp_path, data):
    path = tmp_path / "servers.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


_SAMPLE_CONFIG = {
    "backup_interval": "6h",
    "backup_retention": "7d",
    "mysql_servers": [
        {
            "name": "db1",
            "host": "localhost",
            "user": "root",
            "password": "secret",
            "databases": ["mydb"],
        }
    ],
    "storage_accounts": [
        {
            "name": "acct1",
            "account_name": "myaccount",
            "account_key": "key==",
            "blobs": ["container1"],
        }
    ],
}


# ---------------------------------------------------------------------------
# read_raw_config
# ---------------------------------------------------------------------------

class TestReadRawConfig:
    def test_reads_valid_json(self, tmp_path):
        path = _write_json(tmp_path, _SAMPLE_CONFIG)
        config = read_raw_config(path)
        assert config["backup_interval"] == "6h"
        assert len(config["mysql_servers"]) == 1

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_raw_config(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# write_config
# ---------------------------------------------------------------------------

class TestWriteConfig:
    def test_round_trip(self, tmp_path):
        path = _write_json(tmp_path, _SAMPLE_CONFIG)
        config = read_raw_config(path)
        write_config(config, path)
        reloaded = read_raw_config(path)
        assert reloaded == config

    def test_strips_internal_keys(self, tmp_path):
        path = tmp_path / "servers.json"
        config = {
            "mysql_servers": [
                {
                    "name": "db1",
                    "host": "localhost",
                    "user": "root",
                    "password": "secret",
                    "databases": ["mydb"],
                    "_interval": 3600,
                    "_retention": 86400,
                }
            ]
        }
        write_config(config, path)
        reloaded = read_raw_config(path)
        src = reloaded["mysql_servers"][0]
        assert "_interval" not in src
        assert "_retention" not in src
        assert src["name"] == "db1"


# ---------------------------------------------------------------------------
# get_source_by_name
# ---------------------------------------------------------------------------

class TestGetSourceByName:
    def test_finds_mysql_source(self):
        source, stype = get_source_by_name(_SAMPLE_CONFIG, "db1")
        assert source is not None
        assert stype == "mysql"
        assert source["host"] == "localhost"

    def test_finds_azure_source(self):
        source, stype = get_source_by_name(_SAMPLE_CONFIG, "acct1")
        assert source is not None
        assert stype == "azure"

    def test_returns_none_for_missing(self):
        source, stype = get_source_by_name(_SAMPLE_CONFIG, "nonexistent")
        assert source is None
        assert stype is None


# ---------------------------------------------------------------------------
# add_source
# ---------------------------------------------------------------------------

class TestAddSource:
    def test_add_mysql(self):
        config = {"mysql_servers": []}
        new = {"name": "db2", "host": "10.0.0.1", "user": "admin", "password": "pw", "databases": ["app"]}
        add_source(config, "mysql", new)
        assert len(config["mysql_servers"]) == 1
        assert config["mysql_servers"][0]["name"] == "db2"

    def test_add_azure(self):
        config = {}
        new = {"name": "acct2", "account_name": "sa", "account_key": "k==", "blobs": ["c1"]}
        add_source(config, "azure", new)
        assert len(config["storage_accounts"]) == 1

    def test_add_creates_key_if_missing(self):
        config = {}
        new = {"name": "db1", "host": "h", "user": "u", "password": "p", "databases": ["d"]}
        add_source(config, "mysql", new)
        assert "mysql_servers" in config


# ---------------------------------------------------------------------------
# update_source
# ---------------------------------------------------------------------------

class TestUpdateSource:
    def test_update_replaces_by_name(self):
        config = dict(_SAMPLE_CONFIG)
        config["mysql_servers"] = list(config["mysql_servers"])
        new_data = {"name": "db1", "host": "newhost", "user": "root", "password": "new", "databases": ["newdb"]}
        update_source(config, "db1", "mysql", new_data)
        assert config["mysql_servers"][0]["host"] == "newhost"

    def test_update_nonexistent_does_nothing(self):
        config = dict(_SAMPLE_CONFIG)
        config["mysql_servers"] = list(config["mysql_servers"])
        update_source(config, "missing", "mysql", {"name": "missing"})
        assert len(config["mysql_servers"]) == 1


# ---------------------------------------------------------------------------
# delete_source
# ---------------------------------------------------------------------------

class TestDeleteSource:
    def test_delete_removes_source(self):
        config = dict(_SAMPLE_CONFIG)
        config["mysql_servers"] = list(config["mysql_servers"])
        delete_source(config, "db1")
        assert len(config["mysql_servers"]) == 0

    def test_delete_nonexistent_does_nothing(self):
        config = dict(_SAMPLE_CONFIG)
        config["mysql_servers"] = list(config["mysql_servers"])
        delete_source(config, "nonexistent")
        assert len(config["mysql_servers"]) == 1

    def test_delete_azure_source(self):
        config = dict(_SAMPLE_CONFIG)
        config["storage_accounts"] = list(config["storage_accounts"])
        delete_source(config, "acct1")
        assert len(config["storage_accounts"]) == 0
