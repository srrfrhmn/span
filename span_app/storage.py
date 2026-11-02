from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

MAX_HABITS = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS completions (
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    PRIMARY KEY (habit_id, day)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_targets (
    day TEXT PRIMARY KEY,
    total INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS completions_day ON completions(day);
CREATE INDEX IF NOT EXISTS habits_active ON habits(archived, position);
"""


@dataclass(frozen=True)
class Habit:
    id: int
    name: str
    position: int


def default_data_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "span"


class Store:
    """Local SQLite store.

    A single connection is kept open for the lifetime of the store. Opening a
    connection (and committing) per operation is correct but expensive: each
    commit forces an fsync, which is orders of magnitude slower than reusing a
    warm connection. WAL mode with ``synchronous=NORMAL`` keeps commits cheap
    while remaining safe against application crashes.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_data_dir() / "span.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._depth = 0
        self._db: sqlite3.Connection | None = self._connect()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        try:
            db.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            # Some filesystems (network shares, read-only media) do not support
            # WAL. The default journal mode still works, just slower.
            pass
        db.execute("PRAGMA synchronous = NORMAL")
        return db

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield the shared connection, committing once the outermost block ends.

        Blocks may be nested; only the outermost one commits or rolls back.
        """
        db = self._db
        if db is None:
            raise sqlite3.ProgrammingError("store is closed")
        self._depth += 1
        try:
            yield db
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                db.rollback()
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                db.commit()

    def close(self) -> None:
        if self._db is not None:
            db, self._db = self._db, None
            try:
                db.commit()
            except sqlite3.Error:
                db.rollback()
            finally:
                db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _initialize(self) -> None:
        with self.connection() as db:
            db.executescript(SCHEMA)
            stored = {
                row["key"]: row["value"]
                for row in db.execute("SELECT key, value FROM settings").fetchall()
            }
            defaults = {
                "start_date": date.today().isoformat(),
                "theme": "forest",
                "lifespan": 85,
                "birth_date": date(date.today().year - 30, 1, 1).isoformat(),
            }
            missing = [
                (key, json.dumps(value))
                for key, value in defaults.items()
                if key not in stored
            ]
            if missing:
                db.executemany(
                    """
                    INSERT INTO settings(key, value) VALUES(?, ?)
                    ON CONFLICT(key) DO NOTHING
                    """,
                    missing,
                )

    def get_setting(self, key: str, default=None):
        with self.connection() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, ValueError):
            return default

    def set_setting(self, key: str, value) -> None:
        self.set_settings({key: value})

    def set_settings(self, values: dict) -> None:
        payload = [(key, json.dumps(value)) for key, value in values.items()]
        with self.connection() as db:
            db.executemany(
                """
                INSERT INTO settings(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                payload,
            )

    def habits(self) -> list[Habit]:
        with self.connection() as db:
            rows = db.execute(
                """
                SELECT id, name, position
                FROM habits
                WHERE archived = 0
                ORDER BY position, id
                """
            ).fetchall()
        return [Habit(row["id"], row["name"], row["position"]) for row in rows]

    def replace_habits(self, names: list[str]) -> None:
        clean = [name.strip() for name in names if name.strip()]
        self._validate(clean)

        existing = self.habits()
        items = [
            (existing[position].id if position < len(existing) else None, name)
            for position, name in enumerate(clean)
        ]
        self.save_habits(items)

    def save_habits(self, items: list[tuple[int | None, str]]) -> None:
        clean = [(habit_id, name.strip()) for habit_id, name in items if name.strip()]
        self._validate(clean)

        with self.connection() as db:
            active_ids = {
                row["id"]
                for row in db.execute(
                    "SELECT id FROM habits WHERE archived = 0"
                ).fetchall()
            }
            kept_ids: set[int] = set()
            for position, (habit_id, name) in enumerate(clean):
                if habit_id in active_ids and habit_id not in kept_ids:
                    db.execute(
                        "UPDATE habits SET name = ?, position = ? WHERE id = ?",
                        (name, position, habit_id),
                    )
                    kept_ids.add(habit_id)
                else:
                    cursor = db.execute(
                        "INSERT INTO habits(name, position) VALUES(?, ?)",
                        (name, position),
                    )
                    kept_ids.add(cursor.lastrowid)
            for habit_id in active_ids - kept_ids:
                db.execute("UPDATE habits SET archived = 1 WHERE id = ?", (habit_id,))
            db.execute(
                """
                INSERT INTO daily_targets(day, total) VALUES(?, ?)
                ON CONFLICT(day) DO UPDATE SET total = excluded.total
                """,
                (date.today().isoformat(), len(clean)),
            )

    @staticmethod
    def _validate(names) -> None:
        if not 1 <= len(names) <= MAX_HABITS:
            raise ValueError(f"Choose between 1 and {MAX_HABITS} habits.")

    def completed_ids(self, day: date) -> set[int]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT habit_id FROM completions WHERE day = ?",
                (day.isoformat(),),
            ).fetchall()
        return {row["habit_id"] for row in rows}

    def toggle(self, habit_id: int, day: date) -> bool:
        key = (habit_id, day.isoformat())
        with self.connection() as db:
            removed = db.execute(
                "DELETE FROM completions WHERE habit_id = ? AND day = ?", key
            ).rowcount
            if removed:
                return False
            total = db.execute(
                "SELECT COUNT(*) AS count FROM habits WHERE archived = 0"
            ).fetchone()["count"]
            db.execute(
                """
                INSERT INTO daily_targets(day, total) VALUES(?, ?)
                ON CONFLICT(day) DO NOTHING
                """,
                (day.isoformat(), total),
            )
            db.execute("INSERT INTO completions(habit_id, day) VALUES(?, ?)", key)
            return True

    def _daily_counts(
        self, db: sqlite3.Connection, start: date, end: date
    ) -> dict[date, int]:
        rows = db.execute(
            """
            SELECT day, COUNT(*) AS count
            FROM completions
            WHERE day BETWEEN ? AND ?
            GROUP BY day
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return {date.fromisoformat(row["day"]): row["count"] for row in rows}

    def _daily_targets(
        self, db: sqlite3.Connection, start: date, end: date
    ) -> dict[date, int]:
        rows = db.execute(
            """
            SELECT day, total
            FROM daily_targets
            WHERE day BETWEEN ? AND ?
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return {date.fromisoformat(row["day"]): row["total"] for row in rows}

    def daily_counts(self, start: date, end: date) -> dict[date, int]:
        with self.connection() as db:
            return self._daily_counts(db, start, end)

    def daily_targets(self, start: date, end: date) -> dict[date, int]:
        with self.connection() as db:
            return self._daily_targets(db, start, end)

    def daily_summary(
        self, start: date, end: date
    ) -> tuple[dict[date, int], dict[date, int]]:
        """Return completion counts and targets for a range in one transaction."""
        with self.connection() as db:
            return (
                self._daily_counts(db, start, end),
                self._daily_targets(db, start, end),
            )

    def streak(self, through: date | None = None) -> int:
        through = through or date.today()
        with self.connection() as db:
            habits = db.execute(
                "SELECT COUNT(*) AS count FROM habits WHERE archived = 0"
            ).fetchone()["count"]
            if not habits:
                return 0
            row = db.execute(
                "SELECT value FROM settings WHERE key = 'start_date'"
            ).fetchone()
            try:
                start = date.fromisoformat(json.loads(row["value"]))
            except (TypeError, ValueError):
                start = through
            if start > through:
                return 0
            counts = self._daily_counts(db, start, through)
            targets = self._daily_targets(db, start, through)

        cursor = through
        if counts.get(cursor, 0) < targets.get(cursor, habits):
            cursor -= timedelta(days=1)
        streak = 0
        while (
            cursor >= start
            and counts.get(cursor, 0) >= targets.get(cursor, habits)
        ):
            streak += 1
            cursor -= timedelta(days=1)
        return streak
