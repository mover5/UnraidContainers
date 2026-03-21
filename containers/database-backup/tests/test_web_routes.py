"""Tests for backup.web.routes — Flask route handlers."""

import json
from unittest.mock import patch

import pytest

from backup.state import SchedulerState
from backup.web import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config():
    return {
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
        "storage_accounts": [],
    }


@pytest.fixture
def config_path(tmp_path, sample_config):
    path = tmp_path / "servers.json"
    path.write_text(json.dumps(sample_config), encoding="utf-8")
    return path


@pytest.fixture
def app(config_path):
    application = create_app()
    application.config["TESTING"] = True
    with patch("backup.web.config_manager.CONFIG_PATH", config_path), \
         patch("backup.web.routes.config_manager.CONFIG_PATH", config_path):
        yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fresh_state():
    """Provide a fresh SchedulerState and patch shared_state."""
    state = SchedulerState()
    with patch("backup.web.routes.shared_state", state):
        yield state


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_renders(self, client, fresh_state):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"db1" in resp.data
        assert b"mysql" in resp.data

    def test_dashboard_empty_config(self, client, config_path, fresh_state):
        config_path.write_text(json.dumps({}), encoding="utf-8")
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"No backup sources configured" in resp.data

    def test_dashboard_shows_status(self, client, fresh_state):
        fresh_state.update_source("db1", source_type="mysql", is_running=True)
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"running" in resp.data


# ---------------------------------------------------------------------------
# Source detail
# ---------------------------------------------------------------------------

class TestSourceDetail:
    def test_source_detail_renders(self, client, fresh_state):
        resp = client.get("/source/db1")
        assert resp.status_code == 200
        assert b"db1" in resp.data
        assert b"localhost" in resp.data

    def test_source_detail_missing_redirects(self, client, fresh_state):
        resp = client.get("/source/nonexistent", follow_redirects=True)
        assert resp.status_code == 200
        assert b"not found" in resp.data


# ---------------------------------------------------------------------------
# Manual backup trigger
# ---------------------------------------------------------------------------

class TestTriggerBackup:
    def test_trigger_enqueues_and_redirects(self, client, fresh_state):
        resp = client.post("/source/db1/backup", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Manual backup requested" in resp.data
        # Trigger was consumed by the state
        triggers = fresh_state.pop_manual_triggers()
        assert "db1" in triggers


# ---------------------------------------------------------------------------
# Add source
# ---------------------------------------------------------------------------

class TestAddSource:
    def test_add_form_renders(self, client, fresh_state):
        resp = client.get("/source/add/mysql")
        assert resp.status_code == 200
        assert b"Add" in resp.data
        assert b"mysql" in resp.data

    def test_add_mysql_source(self, client, config_path, fresh_state):
        resp = client.post("/source/add/mysql", data={
            "name": "db2",
            "host": "10.0.0.1",
            "port": "3306",
            "user": "admin",
            "password": "pw",
            "databases": "app_db",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"added successfully" in resp.data

        # Verify config was written
        config = json.loads(config_path.read_text())
        names = [s["name"] for s in config["mysql_servers"]]
        assert "db2" in names

    def test_add_duplicate_name_shows_error(self, client, fresh_state):
        resp = client.post("/source/add/mysql", data={
            "name": "db1",
            "host": "h",
            "port": "3306",
            "user": "u",
            "password": "p",
            "databases": "d",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"already exists" in resp.data

    def test_add_validation_error_shown(self, client, fresh_state):
        resp = client.post("/source/add/mysql", data={
            "name": "db_new",
            "host": "",
            "port": "3306",
            "user": "",
            "password": "",
            "databases": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"required" in resp.data

    def test_add_unknown_type_redirects(self, client, fresh_state):
        resp = client.get("/source/add/unknown", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Unknown source type" in resp.data

    def test_add_azure_source(self, client, config_path, fresh_state):
        resp = client.post("/source/add/azure", data={
            "name": "acct1",
            "account_name": "mystorage",
            "account_key": "key==",
            "blobs": "container1",
            "files": "",
            "tables": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"added successfully" in resp.data

        config = json.loads(config_path.read_text())
        assert len(config["storage_accounts"]) == 1


# ---------------------------------------------------------------------------
# Edit source
# ---------------------------------------------------------------------------

class TestEditSource:
    def test_edit_form_renders(self, client, fresh_state):
        resp = client.get("/source/db1/edit")
        assert resp.status_code == 200
        assert b"Edit" in resp.data
        assert b"localhost" in resp.data

    def test_edit_source_saves(self, client, config_path, fresh_state):
        resp = client.post("/source/db1/edit", data={
            "name": "db1",
            "host": "newhost",
            "port": "3307",
            "user": "root",
            "password": "newsecret",
            "databases": "mydb, otherdb",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"updated successfully" in resp.data

        config = json.loads(config_path.read_text())
        assert config["mysql_servers"][0]["host"] == "newhost"

    def test_edit_missing_source_redirects(self, client, fresh_state):
        resp = client.get("/source/nonexistent/edit", follow_redirects=True)
        assert resp.status_code == 200
        assert b"not found" in resp.data


# ---------------------------------------------------------------------------
# Delete source
# ---------------------------------------------------------------------------

class TestDeleteSource:
    def test_delete_confirm_renders(self, client, fresh_state):
        resp = client.get("/source/db1/delete")
        assert resp.status_code == 200
        assert b"Are you sure" in resp.data
        assert b"db1" in resp.data

    def test_delete_removes_source(self, client, config_path, fresh_state):
        resp = client.post("/source/db1/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert b"deleted" in resp.data

        config = json.loads(config_path.read_text())
        assert len(config["mysql_servers"]) == 0

    def test_delete_missing_source_redirects(self, client, fresh_state):
        resp = client.get("/source/nonexistent/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert b"not found" in resp.data
