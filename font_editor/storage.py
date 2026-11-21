"""SQLite persistence. One connection per operation; writes use BEGIN IMMEDIATE."""

import contextlib
import json
import os
import sqlite3
from datetime import datetime, timezone

from .validation import MAX_FONTS

DB_NAME = "fonts.sqlite3"


class StorageError(Exception):
    """Startup/storage failure (bad data dir, newer schema)."""


class NotFound(Exception):
    pass


class DuplicateTitle(Exception):
    pass


class LimitReached(Exception):
    pass


class StaleVersion(Exception):
    def __init__(self, current):
        super().__init__("stale version")
        self.current = current


class ValidationFailed(Exception):
    def __init__(self, details):
        super().__init__("validation failed")
        self.details = details


_MIGRATION_1 = [
    """CREATE TABLE fonts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(title) BETWEEN 1 AND 60),
  cap_height INTEGER NOT NULL CHECK(cap_height BETWEEN 300 AND 1000),
  version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE glyphs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  font_id INTEGER NOT NULL REFERENCES fonts(id) ON DELETE CASCADE,
  name TEXT NOT NULL COLLATE NOCASE CHECK(length(name) BETWEEN 1 AND 24),
  advance INTEGER NOT NULL CHECK(advance BETWEEN 100 AND 1500),
  points_json TEXT NOT NULL,
  position INTEGER NOT NULL,
  UNIQUE(font_id, name), UNIQUE(font_id, position))""",
]

# Ordered; index i holds the statements taking user_version i -> i+1.
MIGRATIONS = [_MIGRATION_1]
SCHEMA_VERSION = len(MIGRATIONS)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _points_json(points):
    return json.dumps(
        [{"x": p["x"], "y": p["y"]} for p in points], separators=(",", ":"), ensure_ascii=True
    )


class Storage:
    def __init__(self, data_dir):
        if not isinstance(data_dir, (str, os.PathLike)) or str(data_dir) == "":
            raise StorageError("data directory path is empty")
        self.data_dir = os.fspath(data_dir)
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except OSError as e:
            raise StorageError(f"cannot create data directory: {e.strerror or e}") from e
        if not os.path.isdir(self.data_dir):
            raise StorageError("data directory path is not a directory")
        self.path = os.path.join(self.data_dir, DB_NAME)
        try:
            self._migrate()
        except sqlite3.Error as e:
            raise StorageError(f"cannot open database: {e}") from e

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
        except BaseException:
            conn.close()
            raise
        return conn

    @contextlib.contextmanager
    def _txn(self):
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                with contextlib.suppress(sqlite3.Error):
                    conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        finally:
            conn.close()

    def _migrate(self):
        with self._txn() as conn:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            if current > SCHEMA_VERSION:
                raise StorageError(
                    f"database schema version {current} is newer than supported {SCHEMA_VERSION}"
                )
            for target in range(current, SCHEMA_VERSION):
                for stmt in MIGRATIONS[target]:
                    conn.execute(stmt)
                conn.execute(f"PRAGMA user_version={target + 1}")

    def schema_version(self):
        with contextlib.closing(self._connect()) as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def checkpoint(self):
        try:
            with contextlib.closing(self._connect()) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except (sqlite3.Error, OSError):
            pass

    # ---- reads ----
    def list_fonts(self):
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT f.id, f.title, f.version, f.updated_at,
                          (SELECT COUNT(*) FROM glyphs g WHERE g.font_id = f.id) AS glyph_count
                   FROM fonts f ORDER BY f.title COLLATE NOCASE, f.id"""
            ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "version": r["version"],
                "glyph_count": r["glyph_count"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def get_font(self, font_id):
        with contextlib.closing(self._connect()) as conn:
            conn.execute("BEGIN")
            try:
                font = self._load(conn, font_id)
            finally:
                conn.execute("COMMIT")
        if font is None:
            raise NotFound()
        return font

    @staticmethod
    def _load(conn, font_id):
        r = conn.execute("SELECT * FROM fonts WHERE id=?", (font_id,)).fetchone()
        if r is None:
            return None
        glyphs = [
            {
                "id": g["id"],
                "name": g["name"],
                "advance": g["advance"],
                "points": json.loads(g["points_json"]),
            }
            for g in conn.execute(
                "SELECT id,name,advance,points_json FROM glyphs WHERE font_id=? ORDER BY position",
                (font_id,),
            )
        ]
        return {
            "id": r["id"],
            "title": r["title"],
            "cap_height": r["cap_height"],
            "version": r["version"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "glyphs": glyphs,
        }

    @staticmethod
    def _title_taken(conn, title, exclude_id=None):
        key = title.casefold()
        for r in conn.execute("SELECT id, title FROM fonts"):
            if r["id"] != exclude_id and r["title"].casefold() == key:
                return True
        return False

    # ---- writes ----
    def create_font(self, clean):
        try:
            with self._txn() as conn:
                count = conn.execute("SELECT COUNT(*) FROM fonts").fetchone()[0]
                if count >= MAX_FONTS:
                    raise LimitReached()
                if self._title_taken(conn, clean["title"]):
                    raise DuplicateTitle()
                if any("id" in g for g in clean["glyphs"]):
                    raise ValidationFailed(
                        [
                            {"field": f"glyphs[{i}].id", "message": "id is not allowed for a new font"}
                            for i, g in enumerate(clean["glyphs"])
                            if "id" in g
                        ][:50]
                    )
                now = _now()
                cur = conn.execute(
                    "INSERT INTO fonts(title,cap_height,version,created_at,updated_at)"
                    " VALUES(?,?,1,?,?)",
                    (clean["title"], clean["cap_height"], now, now),
                )
                font_id = cur.lastrowid
                for pos, g in enumerate(clean["glyphs"]):
                    conn.execute(
                        "INSERT INTO glyphs(font_id,name,advance,points_json,position)"
                        " VALUES(?,?,?,?,?)",
                        (font_id, g["name"], g["advance"], _points_json(g["points"]), pos),
                    )
                return self._load(conn, font_id)
        except sqlite3.IntegrityError as e:
            if "fonts.title" in str(e):
                raise DuplicateTitle() from e
            raise

    def replace_font(self, font_id, clean):
        try:
            with self._txn() as conn:
                row = conn.execute("SELECT version FROM fonts WHERE id=?", (font_id,)).fetchone()
                if row is None:
                    raise NotFound()
                if row["version"] != clean["version"]:
                    raise StaleVersion(self._load(conn, font_id))
                existing = {
                    r["id"]
                    for r in conn.execute("SELECT id FROM glyphs WHERE font_id=?", (font_id,))
                }
                bad = [
                    {"field": f"glyphs[{i}].id", "message": "id does not belong to this font"}
                    for i, g in enumerate(clean["glyphs"])
                    if "id" in g and g["id"] not in existing
                ]
                if bad:
                    raise ValidationFailed(bad[:50])
                if self._title_taken(conn, clean["title"], exclude_id=font_id):
                    raise DuplicateTitle()

                kept = {g["id"] for g in clean["glyphs"] if "id" in g}
                for gid in existing - kept:
                    conn.execute("DELETE FROM glyphs WHERE id=? AND font_id=?", (gid, font_id))
                # Park survivors on unique temporary values so swaps cannot collide.
                for gid in kept:
                    conn.execute(
                        "UPDATE glyphs SET name=?, position=? WHERE id=? AND font_id=?",
                        ("\x01" + str(gid), -gid, gid, font_id),
                    )
                for pos, g in enumerate(clean["glyphs"]):
                    if "id" in g:
                        conn.execute(
                            "UPDATE glyphs SET name=?, advance=?, points_json=?, position=?"
                            " WHERE id=? AND font_id=?",
                            (g["name"], g["advance"], _points_json(g["points"]), pos, g["id"], font_id),
                        )
                    else:
                        conn.execute(
                            "INSERT INTO glyphs(font_id,name,advance,points_json,position)"
                            " VALUES(?,?,?,?,?)",
                            (font_id, g["name"], g["advance"], _points_json(g["points"]), pos),
                        )
                conn.execute(
                    "UPDATE fonts SET title=?, cap_height=?, version=version+1, updated_at=?"
                    " WHERE id=?",
                    (clean["title"], clean["cap_height"], _now(), font_id),
                )
                return self._load(conn, font_id)
        except sqlite3.IntegrityError as e:
            if "fonts.title" in str(e):
                raise DuplicateTitle() from e
            raise
