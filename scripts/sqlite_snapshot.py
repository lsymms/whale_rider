"""Create and restore verified SQLite snapshots without copying WAL files directly."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import shutil
import sqlite3
import sys
import time
import uuid
from pathlib import Path


class SnapshotError(ValueError):
    pass


def host_local(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    raw = str(resolved)
    if raw.startswith("\\\\") or raw.startswith("//"):
        raise SnapshotError("Network paths are not allowed for SQLite runtime or backups.")
    if os.name == "nt" and resolved.drive:
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(f"{resolved.drive}\\") == 4:
                raise SnapshotError("Mapped network drives are not allowed for SQLite runtime or backups.")
        except AttributeError:
            pass
    return resolved


def sqlite_backup(source: Path, destination: Path) -> None:
    source_uri = f"file:{source.as_posix()}?mode=ro"
    read_connection = sqlite3.connect(source_uri, uri=True)
    write_connection = sqlite3.connect(destination)
    try:
        read_connection.backup(write_connection)
        result = write_connection.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            raise SnapshotError("SQLite integrity check failed for the staged snapshot.")
    finally:
        write_connection.close()
        read_connection.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_with_retry(source: Path, destination: Path) -> None:
    """Allow short antivirus/indexer handle churn on Windows runtime files."""
    last_error: OSError | None = None
    for attempt in range(5):
        try:
            os.replace(source, destination)
            return
        except PermissionError as error:
            last_error = error
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))
    if last_error:
        raise last_error


def backup(source: Path, destination: Path) -> None:
    source, destination = host_local(source), host_local(destination)
    if not source.is_file():
        raise SnapshotError("Source SQLite database does not exist.")
    if destination.exists():
        raise SnapshotError("Backup destination already exists; choose a new explicit filename.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sqlite_backup(source, destination)
    destination.with_suffix(destination.suffix + ".sha256").write_text(f"{sha256(destination)}  {destination.name}\n", encoding="ascii")
    print(f"Backup verified: {destination.name}")


def restore(source: Path, destination: Path, force: bool) -> None:
    source, destination = host_local(source), host_local(destination)
    if not source.is_file():
        raise SnapshotError("Backup SQLite database does not exist.")
    if destination.name != "whale-rider.sqlite3":
        raise SnapshotError("Restore destination must be the explicit whale-rider.sqlite3 runtime database.")
    if destination.exists() and not force:
        raise SnapshotError("Runtime database exists; rerun with --force after stopping the local service.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_name(f".{destination.stem}.restore-{uuid.uuid4().hex}{destination.suffix}")
    try:
        sqlite_backup(source, staged)
        previous = None
        if destination.exists():
            previous = destination.with_name(f"{destination.stem}.pre-restore-{uuid.uuid4().hex}{destination.suffix}")
            replace_with_retry(destination, previous)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(destination) + suffix)
            if sidecar.exists():
                replace_with_retry(sidecar, sidecar.with_name(f"{sidecar.name}.pre-restore-{uuid.uuid4().hex}"))
        replace_with_retry(staged, destination)
    finally:
        if staged.exists():
            staged.unlink()
    message = "Restore verified"
    if previous is not None:
        message += f"; previous database retained as {previous.name}"
    print(message + ".")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in (commands.add_parser("backup"), commands.add_parser("restore")):
        command.add_argument("--source", required=True, type=Path)
        command.add_argument("--destination", required=True, type=Path)
    commands.choices["restore"].add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            backup(args.source, args.destination)
        else:
            restore(args.source, args.destination, args.force)
    except (SnapshotError, sqlite3.Error, OSError) as error:
        print(f"Snapshot failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
