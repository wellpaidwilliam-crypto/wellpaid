"""WellPaiD Trader - Atomic persistence helpers.

JSON stores must never be left half-written by a crash or power loss.
`atomic_write_json` writes to a temp file in the same directory, fsyncs,
then atomically replaces the target via `os.replace` (atomic on both
Windows and POSIX when source and destination share a directory).
"""

import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Union


def atomic_write_json(path: Union[str, Path], data: Any) -> None:
    """Write JSON data atomically.

    Args:
        path: Destination file path.
        data: JSON-serializable data.

    Raises:
        OSError: If the write or replace fails. The original file,
            if any, is left untouched.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=target.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


SQLITE_MAGIC = b"SQLite format 3\x00"


def sqlite_connect(path: Union[str, Path]) -> sqlite3.Connection:
    """Open a SQLite database, migrating a legacy JSON file aside.

    If a non-SQLite file already exists at `path` (e.g. a V1 JSON store),
    it is renamed to `<name>.bak` and a fresh database is created, so an
    old store can never corrupt the new backend. Data migration from the
    legacy format is intentionally NOT attempted: V1 stores were
    explicitly research-grade.

    Args:
        path: Database file path.

    Returns:
        An sqlite3 connection with Row factory enabled.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        with open(target, "rb") as f:
            if f.read(len(SQLITE_MAGIC)) != SQLITE_MAGIC:
                target.replace(target.with_name(target.name + ".bak"))
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def sqlite_db(path: Union[str, Path]) -> Iterator[sqlite3.Connection]:
    """Open a SQLite database, commit on success, always close.

    `sqlite3.Connection` as a context manager only scopes transactions —
    it never closes the handle, which locks the file on Windows. Use
    this helper for every access so files are never left locked.

    Args:
        path: Database file path (see `sqlite_connect` for migration).

    Yields:
        An open connection, committed on clean exit, closed always.
    """
    conn = sqlite_connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()
