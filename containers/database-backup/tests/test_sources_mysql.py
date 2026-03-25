"""Tests for backup.sources.mysql — validate and backup_dir."""
import gzip
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backup.sources import mysql


# Global defaults used across tests
_GLOBAL_INTERVAL = 86400   # 24h
_GLOBAL_RETENTION = 30


def _valid_source(**overrides):
    src = {
        "name": "db1",
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "secret",
        "databases": ["mydb"],
    }
    src.update(overrides)
    return src


# ---------------------------------------------------------------------------
# backup_dir
# ---------------------------------------------------------------------------

class TestBackupDir:
    def test_returns_path_under_mysql_dir(self):
        result = mysql.backup_dir("myserver")
        assert result.parts[-1] == "myserver"
        assert "mysql" in result.parts

    def test_different_names_give_different_paths(self):
        assert mysql.backup_dir("a") != mysql.backup_dir("b")


# ---------------------------------------------------------------------------
# validate — happy path
# ---------------------------------------------------------------------------

class TestMysqlValidateValid:
    def test_valid_source_no_errors(self):
        src = _valid_source()
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert errors == []

    def test_default_port_applied(self):
        src = _valid_source()
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert src["port"] == 3306

    def test_explicit_port_preserved(self):
        src = _valid_source(port=3307)
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert src["port"] == 3307

    def test_inherits_global_interval(self):
        src = _valid_source()
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert src["_interval"] == _GLOBAL_INTERVAL
        assert src["_retention"] == _GLOBAL_RETENTION

    def test_per_source_interval_override(self):
        src = _valid_source(backup_interval="30m", backup_retention="3")
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert errors == []
        assert src["_interval"] == 30 * 60
        assert src["_retention"] == 3


# ---------------------------------------------------------------------------
# validate — error cases
# ---------------------------------------------------------------------------

class TestMysqlValidateErrors:
    def test_missing_name(self):
        src = _valid_source()
        del src["name"]
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("name" in e for e in errors)

    def test_missing_host(self):
        src = _valid_source()
        del src["host"]
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("host" in e for e in errors)

    def test_missing_user(self):
        src = _valid_source()
        del src["user"]
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("user" in e for e in errors)

    def test_missing_password(self):
        src = _valid_source()
        del src["password"]
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("password" in e for e in errors)

    def test_missing_databases(self):
        src = _valid_source()
        del src["databases"]
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("databases" in e for e in errors)

    def test_empty_databases_list(self):
        src = _valid_source(databases=[])
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("databases" in e for e in errors)

    def test_invalid_interval_appends_error_and_uses_global(self):
        src = _valid_source(backup_interval="bad")
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert len(errors) == 1
        assert src["_interval"] == _GLOBAL_INTERVAL

    def test_invalid_retention_appends_error_and_uses_global(self):
        src = _valid_source(backup_retention="bad")
        errors = []
        mysql.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert len(errors) == 1
        assert src["_retention"] == _GLOBAL_RETENTION

    def test_index_shown_in_error_message(self):
        src = _valid_source()
        del src["name"]
        errors = []
        mysql.validate(src, 2, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("#3" in e for e in errors)


# ---------------------------------------------------------------------------
# run_backup
# ---------------------------------------------------------------------------

class TestMysqlRunBackup:
    def test_successful_backup_creates_file(self, tmp_path):
        src = _valid_source()
        fake_sql = b"SELECT 1;"

        with patch("backup.sources.mysql._MYSQL_DIR", tmp_path), \
             patch("backup.sources.mysql.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_sql)
            mysql.run_backup(src)

        server_dir = tmp_path / "db1"
        files = list(server_dir.glob("*.sql.gz"))
        assert len(files) == 1
        assert gzip.decompress(files[0].read_bytes()) == fake_sql

    def test_failed_mysqldump_skips_file(self, tmp_path):
        src = _valid_source()

        with patch("backup.sources.mysql._MYSQL_DIR", tmp_path), \
             patch("backup.sources.mysql.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"error msg")
            mysql.run_backup(src)

        server_dir = tmp_path / "db1"
        assert not server_dir.exists() or list(server_dir.glob("*.sql.gz")) == []

    def test_backup_created_for_each_database(self, tmp_path):
        src = _valid_source(databases=["db_a", "db_b", "db_c"])

        with patch("backup.sources.mysql._MYSQL_DIR", tmp_path), \
             patch("backup.sources.mysql.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"sql")
            mysql.run_backup(src)

        server_dir = tmp_path / "db1"
        files = list(server_dir.glob("*.sql.gz"))
        assert len(files) == 3
