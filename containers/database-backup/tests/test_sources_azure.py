"""Tests for backup.sources.azure — validate, backup_dir, _serialize_table_entity."""
import base64
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from uuid import UUID

import pytest

from backup.sources import azure
from backup.sources.azure import _serialize_table_entity


# Global defaults used across tests
_GLOBAL_INTERVAL = 86400
_GLOBAL_RETENTION = 30


def _valid_source(**overrides):
    src = {
        "name": "acct1",
        "account_name": "myaccount",
        "account_key": "key==",
        "blobs": ["container1"],
        "files": [],
        "tables": [],
    }
    src.update(overrides)
    return src


# ---------------------------------------------------------------------------
# backup_dir
# ---------------------------------------------------------------------------

class TestAzureBackupDir:
    def test_returns_path_under_azure_storage_dir(self):
        result = azure.backup_dir("myaccount")
        assert result.parts[-1] == "myaccount"
        assert "azure-storage" in result.parts

    def test_different_names_give_different_paths(self):
        assert azure.backup_dir("a") != azure.backup_dir("b")


# ---------------------------------------------------------------------------
# validate — happy path
# ---------------------------------------------------------------------------

class TestAzureValidateValid:
    def test_valid_source_no_errors(self):
        src = _valid_source()
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert errors == []

    def test_inherits_global_interval(self):
        src = _valid_source()
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert src["_interval"] == _GLOBAL_INTERVAL
        assert src["_retention"] == _GLOBAL_RETENTION

    def test_per_source_interval_override(self):
        src = _valid_source(backup_interval="1h", backup_retention="7")
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert errors == []
        assert src["_interval"] == 3600
        assert src["_retention"] == 7

    def test_defaults_empty_lists(self):
        src = {
            "name": "acct1",
            "account_name": "myaccount",
            "account_key": "key==",
            "blobs": ["c1"],
        }
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert src.get("files") == []
        assert src.get("tables") == []

    def test_tables_only_is_valid(self):
        src = _valid_source(blobs=[], tables=["t1"])
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert errors == []

    def test_files_only_is_valid(self):
        src = _valid_source(blobs=[], files=["s1"])
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert errors == []


# ---------------------------------------------------------------------------
# validate — error cases
# ---------------------------------------------------------------------------

class TestAzureValidateErrors:
    def test_missing_name(self):
        src = _valid_source()
        del src["name"]
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("name" in e for e in errors)

    def test_missing_account_name(self):
        src = _valid_source()
        del src["account_name"]
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("account_name" in e for e in errors)

    def test_missing_account_key(self):
        src = _valid_source()
        del src["account_key"]
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("account_key" in e for e in errors)

    def test_no_resources_appends_error(self):
        src = _valid_source(blobs=[], files=[], tables=[])
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert len(errors) == 1
        assert "blobs" in errors[0] or "tables" in errors[0] or "files" in errors[0]

    def test_invalid_interval_appends_error_and_uses_global(self):
        src = _valid_source(backup_interval="bad")
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert len(errors) == 1
        assert src["_interval"] == _GLOBAL_INTERVAL

    def test_invalid_retention_appends_error_and_uses_global(self):
        src = _valid_source(backup_retention="bad")
        errors = []
        azure.validate(src, 0, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert len(errors) == 1
        assert src["_retention"] == _GLOBAL_RETENTION

    def test_index_shown_in_error_message(self):
        src = _valid_source(blobs=[], files=[], tables=[])
        errors = []
        azure.validate(src, 2, errors, _GLOBAL_INTERVAL, _GLOBAL_RETENTION)
        assert any("#3" in e for e in errors)


# ---------------------------------------------------------------------------
# _serialize_table_entity
# ---------------------------------------------------------------------------

class TestSerializeTableEntity:
    def test_string_value_passthrough(self):
        result = _serialize_table_entity({"key": "hello"})
        assert result["key"] == "hello"

    def test_int_value_passthrough(self):
        result = _serialize_table_entity({"num": 42})
        assert result["num"] == 42

    def test_datetime_converted_to_isoformat(self):
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = _serialize_table_entity({"ts": dt})
        assert result["ts"] == dt.isoformat()

    def test_bytes_converted_to_base64(self):
        raw = b"\x00\x01\x02"
        result = _serialize_table_entity({"data": raw})
        assert result["data"] == base64.b64encode(raw).decode("ascii")

    def test_uuid_converted_to_string(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        result = _serialize_table_entity({"id": uid})
        assert result["id"] == str(uid)

    def test_mixed_entity(self):
        dt = datetime(2024, 6, 1, tzinfo=timezone.utc)
        uid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        entity = {"RowKey": "r1", "ts": dt, "uid": uid, "data": b"x", "val": 99}
        result = _serialize_table_entity(entity)
        assert result["RowKey"] == "r1"
        assert result["val"] == 99
        assert isinstance(result["ts"], str)
        assert isinstance(result["uid"], str)
        assert isinstance(result["data"], str)
