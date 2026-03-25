"""Tests for backup.scheduler — cleanup_source_backups and _latest_backup_age."""
import time
from pathlib import Path

import pytest

from backup.scheduler import cleanup_source_backups, _latest_backup_age


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _touch(path: Path, age_seconds: float = 0.0):
    """Create a file and set its mtime to `age_seconds` seconds ago."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    mtime = time.time() - age_seconds
    import os
    os.utime(path, (mtime, mtime))
    return path


# ---------------------------------------------------------------------------
# cleanup_source_backups
# ---------------------------------------------------------------------------

class TestCleanupSourceBackups:
    def test_empty_directory_does_nothing(self, tmp_path):
        # No files — should not raise
        cleanup_source_backups(tmp_path, retention_count=5)

    def test_single_file_never_deleted(self, tmp_path):
        """Even with retention_count=1, the single file is kept."""
        f = _touch(tmp_path / "db_2020-01-01_000000.sql.gz", age_seconds=99999)
        cleanup_source_backups(tmp_path, retention_count=1)
        assert f.exists()

    def test_keeps_n_newest_deletes_rest(self, tmp_path):
        old = _touch(tmp_path / "db_old.sql.gz", age_seconds=7200)
        mid = _touch(tmp_path / "db_mid.sql.gz", age_seconds=3600)
        new = _touch(tmp_path / "db_new.sql.gz", age_seconds=60)
        cleanup_source_backups(tmp_path, retention_count=2)
        assert new.exists()
        assert mid.exists()
        assert not old.exists()

    def test_all_kept_when_under_retention(self, tmp_path):
        f1 = _touch(tmp_path / "db_1.sql.gz", age_seconds=100)
        f2 = _touch(tmp_path / "db_2.sql.gz", age_seconds=200)
        cleanup_source_backups(tmp_path, retention_count=5)
        assert f1.exists()
        assert f2.exists()

    def test_retention_count_1_keeps_only_newest(self, tmp_path):
        old = _touch(tmp_path / "db_a.sql.gz", age_seconds=10000)
        new = _touch(tmp_path / "db_b.sql.gz", age_seconds=100)
        cleanup_source_backups(tmp_path, retention_count=1)
        assert new.exists()
        assert not old.exists()

    def test_tar_gz_files_are_cleaned(self, tmp_path):
        new = _touch(tmp_path / "share_new.tar.gz", age_seconds=10)
        old = _touch(tmp_path / "share_old.tar.gz", age_seconds=7200)
        cleanup_source_backups(tmp_path, retention_count=1)
        assert new.exists()
        assert not old.exists()

    def test_json_gz_files_are_cleaned(self, tmp_path):
        new = _touch(tmp_path / "table_new.json.gz", age_seconds=10)
        old = _touch(tmp_path / "table_old.json.gz", age_seconds=7200)
        cleanup_source_backups(tmp_path, retention_count=1)
        assert new.exists()
        assert not old.exists()

    def test_subdirectory_files_are_found(self, tmp_path):
        subdir = tmp_path / "subdir"
        new = _touch(subdir / "db_new.sql.gz", age_seconds=10)
        old = _touch(subdir / "db_old.sql.gz", age_seconds=7200)
        cleanup_source_backups(tmp_path, retention_count=1)
        assert new.exists()
        assert not old.exists()

    def test_always_keeps_at_least_one(self, tmp_path):
        """Even with retention_count=0 (invalid), at least one file is kept."""
        f1 = _touch(tmp_path / "db_1.sql.gz", age_seconds=1000)
        f2 = _touch(tmp_path / "db_2.sql.gz", age_seconds=2000)
        cleanup_source_backups(tmp_path, retention_count=0)
        assert f1.exists()
        assert not f2.exists()


# ---------------------------------------------------------------------------
# _latest_backup_age
# ---------------------------------------------------------------------------

class TestLatestBackupAge:
    def test_empty_directory_returns_none(self, tmp_path):
        assert _latest_backup_age(tmp_path) is None

    def test_returns_approximate_age(self, tmp_path):
        _touch(tmp_path / "db.sql.gz", age_seconds=300)
        age = _latest_backup_age(tmp_path)
        assert age is not None
        assert 290 <= age <= 310  # allow a small window for test timing

    def test_returns_age_of_newest_file(self, tmp_path):
        _touch(tmp_path / "db_old.sql.gz", age_seconds=1000)
        _touch(tmp_path / "db_new.sql.gz", age_seconds=60)
        age = _latest_backup_age(tmp_path)
        assert age is not None
        assert age < 120  # should reflect the newer file

    def test_recognises_tar_gz(self, tmp_path):
        _touch(tmp_path / "share.tar.gz", age_seconds=100)
        assert _latest_backup_age(tmp_path) is not None

    def test_recognises_json_gz(self, tmp_path):
        _touch(tmp_path / "table.json.gz", age_seconds=100)
        assert _latest_backup_age(tmp_path) is not None

    def test_ignores_unrecognised_extensions(self, tmp_path):
        _touch(tmp_path / "notes.txt", age_seconds=10)
        assert _latest_backup_age(tmp_path) is None
