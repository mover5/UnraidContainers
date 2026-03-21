import base64
import gzip
import json
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

from azure.data.tables import TableServiceClient
from azure.storage.blob import BlobServiceClient
from azure.storage.fileshare import ShareServiceClient

from ..common import BACKUP_DIR, log, parse_interval

SOURCE_TYPE = "azure"
CONFIG_KEY = "storage_accounts"
LEGACY_KEYS = []

_AZURE_DIR = BACKUP_DIR / "azure-storage"
_REQUIRED_FIELDS = ("name", "account_name", "account_key")


def backup_dir(source_name):
    """Return the backup directory Path for an Azure Storage account."""
    return _AZURE_DIR / source_name


def validate(source, index, errors, global_interval, global_retention):
    """Validate and mutate an Azure Storage account config dict."""
    for field in _REQUIRED_FIELDS:
        if not source.get(field):
            errors.append(f"Storage account #{index + 1}: '{field}' is required.")
    source.setdefault("blobs", [])
    source.setdefault("files", [])
    source.setdefault("tables", [])
    if not source.get("blobs") and not source.get("files") and not source.get("tables"):
        errors.append(
            f"Storage account #{index + 1}: at least one of 'blobs', 'files', or 'tables' must be non-empty."
        )

    if "backup_interval" in source:
        try:
            source["_interval"] = parse_interval(source["backup_interval"])
        except ValueError as e:
            errors.append(f"Storage account #{index + 1}: {e}")
            source["_interval"] = global_interval
    else:
        source["_interval"] = global_interval

    if "backup_retention" in source:
        try:
            source["_retention"] = parse_interval(source["backup_retention"])
        except ValueError as e:
            errors.append(f"Storage account #{index + 1}: {e}")
            source["_retention"] = global_retention
    else:
        source["_retention"] = global_retention


def _conn_str(source):
    return (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={source['account_name']};"
        f"AccountKey={source['account_key']};"
        f"EndpointSuffix=core.windows.net"
    )


def _backup_blob_container(source, container_name, timestamp):
    """Download all blobs from a container and create a .tar.gz archive."""
    account_dir = _AZURE_DIR / source["name"] / "blobs"
    account_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{container_name}_{timestamp}.tar.gz"
    filepath = account_dir / filename

    log.info("[%s] Backing up blob container '%s'...", source["name"], container_name)

    try:
        blob_service = BlobServiceClient.from_connection_string(_conn_str(source))
        container_client = blob_service.get_container_client(container_name)

        with tempfile.TemporaryDirectory() as tmpdir:
            blob_count = 0
            for blob in container_client.list_blobs():
                blob_path = Path(tmpdir) / blob.name
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                blob_client = container_client.get_blob_client(blob.name)
                with open(blob_path, "wb") as f:
                    stream = blob_client.download_blob()
                    stream.readinto(f)
                blob_count += 1

            with tarfile.open(filepath, "w:gz") as tar:
                for entry in Path(tmpdir).rglob("*"):
                    if entry.is_file():
                        tar.add(entry, arcname=entry.relative_to(tmpdir))

        size_kb = filepath.stat().st_size / 1024
        log.info("[%s] Saved %s (%d blobs, %.1f KB)", source["name"], filename, blob_count, size_kb)

    except Exception:
        log.exception("[%s] Failed to back up blob container '%s'", source["name"], container_name)


def _backup_file_share(source, share_name, timestamp):
    """Recursively download all files from a file share and create a .tar.gz archive."""
    account_dir = _AZURE_DIR / source["name"] / "files"
    account_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{share_name}_{timestamp}.tar.gz"
    filepath = account_dir / filename

    log.info("[%s] Backing up file share '%s'...", source["name"], share_name)

    try:
        share_service = ShareServiceClient.from_connection_string(_conn_str(source))
        share_client = share_service.get_share_client(share_name)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_count = 0

            def download_directory(directory_client, local_dir):
                nonlocal file_count
                for item in directory_client.list_directories_and_files():
                    if item["is_directory"]:
                        sub_dir = Path(local_dir) / item["name"]
                        sub_dir.mkdir(parents=True, exist_ok=True)
                        sub_client = directory_client.get_subdirectory_client(item["name"])
                        download_directory(sub_client, sub_dir)
                    else:
                        file_path = Path(local_dir) / item["name"]
                        file_client = directory_client.get_file_client(item["name"])
                        with open(file_path, "wb") as f:
                            stream = file_client.download_file()
                            stream.readinto(f)
                        file_count += 1

            root_dir = share_client.get_directory_client("")
            download_directory(root_dir, tmpdir)

            with tarfile.open(filepath, "w:gz") as tar:
                for entry in Path(tmpdir).rglob("*"):
                    if entry.is_file():
                        tar.add(entry, arcname=entry.relative_to(tmpdir))

        size_kb = filepath.stat().st_size / 1024
        log.info("[%s] Saved %s (%d files, %.1f KB)", source["name"], filename, file_count, size_kb)

    except Exception:
        log.exception("[%s] Failed to back up file share '%s'", source["name"], share_name)


def _serialize_table_entity(entity):
    """Serialize a table entity dict to JSON-safe types."""
    result = {}
    for key, value in entity.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, bytes):
            result[key] = base64.b64encode(value).decode("ascii")
        elif isinstance(value, UUID):
            result[key] = str(value)
        else:
            result[key] = value
    return result


def _backup_table(source, table_name, timestamp):
    """Export all entities from a table as gzip-compressed JSON."""
    account_dir = _AZURE_DIR / source["name"] / "tables"
    account_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{table_name}_{timestamp}.json.gz"
    filepath = account_dir / filename

    log.info("[%s] Backing up table '%s'...", source["name"], table_name)

    try:
        table_service = TableServiceClient.from_connection_string(_conn_str(source))
        table_client = table_service.get_table_client(table_name)

        entities = [_serialize_table_entity(e) for e in table_client.list_entities()]

        json_bytes = json.dumps(entities, indent=2, default=str).encode("utf-8")
        with open(filepath, "wb") as f:
            f.write(gzip.compress(json_bytes))

        size_kb = filepath.stat().st_size / 1024
        log.info("[%s] Saved %s (%d entities, %.1f KB)", source["name"], filename, len(entities), size_kb)

    except Exception:
        log.exception("[%s] Failed to back up table '%s'", source["name"], table_name)


def run_backup(source):
    """Back up Azure Storage resources (blobs, files, tables) for a single account."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    for container in source["blobs"]:
        _backup_blob_container(source, container, timestamp)

    for share in source["files"]:
        _backup_file_share(source, share, timestamp)

    for table in source["tables"]:
        _backup_table(source, table, timestamp)
