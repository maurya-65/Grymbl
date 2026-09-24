"""SQLite storage: event queue, file snapshots, and the Experience Graph (plan §7).

Plain tables, not a graph database. The two relationships are join tables:
EPISODE --touched--> FILE is `episode_files`; EPISODE --produced--> ASSUMPTION is
`assumptions.source_episode_id`.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Literal

from grymbl.events import Event, EventKind, utcnow

Validity = Literal["valid", "unverified", "contradicted"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episodes (
    episode_id          TEXT PRIMARY KEY,
    timestamp_start     TEXT NOT NULL,
    timestamp_end       TEXT NOT NULL,
    developer           TEXT NOT NULL,
    summary             TEXT,
    had_deletion        INTEGER NOT NULL DEFAULT 0,
    had_fail_retry_pass INTEGER NOT NULL DEFAULT 0,
    escalated           INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    agent               TEXT,  -- coding agent that did the work; NULL for human work (v1.1)
    intent              TEXT,  -- redacted prompt that opened an agent episode (v1.1)
    jev_rules           TEXT,  -- JSON list of rule ids that fired, e.g. ["fail_retry_pass"]
    jev_reasons         TEXT,  -- JSON list of the same, as readable reasons
    intervention        TEXT   -- the warning delivered for this episode, if any
);

CREATE TABLE IF NOT EXISTS events (
    event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    ts         TEXT NOT NULL,
    developer  TEXT NOT NULL,
    files      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    episode_id TEXT REFERENCES episodes (episode_id)
);
CREATE INDEX IF NOT EXISTS events_by_episode ON events (episode_id);

CREATE TABLE IF NOT EXISTS files (
    file_path TEXT PRIMARY KEY,
    imports   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episode_files (
    episode_id TEXT NOT NULL REFERENCES episodes (episode_id),
    file_path  TEXT NOT NULL,
    PRIMARY KEY (episode_id, file_path)
);
CREATE INDEX IF NOT EXISTS episode_files_by_path ON episode_files (file_path);

CREATE TABLE IF NOT EXISTS assumptions (
    assumption_id     TEXT PRIMARY KEY,
    statement         TEXT NOT NULL,
    source_episode_id TEXT NOT NULL REFERENCES episodes (episode_id),
    created_at        TEXT NOT NULL,
    current_validity  TEXT NOT NULL DEFAULT 'unverified'
        CHECK (current_validity IN ('valid', 'unverified', 'contradicted'))
);

-- One row per model call: what it cost, priced when it was made.
CREATE TABLE IF NOT EXISTS model_calls (
    call_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id    TEXT NOT NULL REFERENCES episodes (episode_id),
    ts            TEXT NOT NULL,
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd      REAL
);

-- Last known content per file: the dedup baseline, and the "before" side of diffs.
CREATE TABLE IF NOT EXISTS file_snapshots (
    file_path    TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    content      TEXT NOT NULL
);
"""

# Columns added after v1, applied to databases created before them.
_ADDED_COLUMNS = {
    "episodes": ("agent", "intent", "jev_rules", "jev_reasons", "intervention"),
}


@dataclass(frozen=True)
class Snapshot:
    content_hash: str
    content: str


@dataclass(frozen=True)
class ClosedEpisode:
    episode_id: str
    summary: str | None
    had_deletion: bool
    had_fail_retry_pass: bool
    escalated: bool
    files: tuple[str, ...]
    agent: str | None = None
    intent: str | None = None
    jev_rules: tuple[str, ...] = ()
    jev_reasons: tuple[str, ...] = ()
    intervention: str | None = None


@dataclass(frozen=True)
class PriorEpisode:
    episode_id: str
    timestamp_start: datetime
    files: tuple[str, ...]
    intent: str | None
    summary: str | None
    assumptions: tuple[tuple[str, Validity], ...]


@dataclass(frozen=True)
class EpisodeRow:
    episode_id: str
    timestamp_start: datetime
    timestamp_end: datetime
    developer: str
    status: str
    escalated: bool
    summary: str | None
    files: tuple[str, ...]
    agent: str | None
    intent: str | None
    jev_rules: tuple[str, ...]
    jev_reasons: tuple[str, ...]
    intervention: str | None


@dataclass(frozen=True)
class ModelCall:
    episode_id: str
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


class Store:
    def __init__(self, db_path: Path) -> None:
        self._conn = sqlite3.connect(db_path, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        with self._tx() as conn:
            for table, columns in _ADDED_COLUMNS.items():
                existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
                for column in columns:
                    if column not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._conn:
            yield self._conn

    # --- meta -------------------------------------------------------------

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_meta(self, key: str, value: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def count_call(self, day: str) -> int:
        """Increment and return the number of model calls made on `day` (YYYY-MM-DD, UTC)."""
        key = f"model_calls/{day}"
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, '1') "
                "ON CONFLICT (key) DO UPDATE SET value = CAST(value AS INTEGER) + 1",
                (key,),
            )
        return int(self.get_meta(key) or 0)

    def calls_on(self, day: str) -> int:
        return int(self.get_meta(f"model_calls/{day}") or 0)

    # --- events -----------------------------------------------------------

    def add_event(self, event: Event) -> Event:
        """Persist `event`; returns it with its assigned id."""
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO events (kind, ts, developer, files, payload) VALUES (?, ?, ?, ?, ?)",
                (
                    event.kind.value,
                    event.timestamp.isoformat(),
                    event.developer,
                    json.dumps(list(event.files)),
                    json.dumps(event.payload),
                ),
            )
        return replace(event, event_id=cursor.lastrowid)

    def unassigned_events(self) -> list[Event]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE episode_id IS NULL ORDER BY ts, event_id"
        ).fetchall()
        return [_event_from_row(row) for row in rows]

    def episode_events(self, episode_id: str) -> list[Event]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE episode_id = ? ORDER BY ts, event_id", (episode_id,)
        ).fetchall()
        return [_event_from_row(row) for row in rows]

    def file_events_since(self, since: datetime) -> list[Event]:
        """File changes and deletions from `since` on, in the order snapshots were updated."""
        rows = self._conn.execute(
            "SELECT * FROM events WHERE kind IN (?, ?) AND ts >= ? ORDER BY event_id",
            (EventKind.FILE_CHANGED.value, EventKind.FILE_DELETED.value, since.isoformat()),
        ).fetchall()
        return [_event_from_row(row) for row in rows]

    # --- snapshots & FILE nodes -------------------------------------------

    def snapshot(self, file_path: str) -> Snapshot | None:
        row = self._conn.execute(
            "SELECT content_hash, content FROM file_snapshots WHERE file_path = ?", (file_path,)
        ).fetchone()
        return None if row is None else Snapshot(row["content_hash"], row["content"])

    def put_snapshot(self, file_path: str, snapshot: Snapshot, imports: Iterable[str]) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO file_snapshots (file_path, content_hash, content) VALUES (?, ?, ?) "
                "ON CONFLICT (file_path) DO UPDATE SET "
                "content_hash = excluded.content_hash, content = excluded.content",
                (file_path, snapshot.content_hash, snapshot.content),
            )
            conn.execute(
                "INSERT INTO files (file_path, imports) VALUES (?, ?) "
                "ON CONFLICT (file_path) DO UPDATE SET imports = excluded.imports",
                (file_path, json.dumps(sorted(imports))),
            )

    def delete_snapshot(self, file_path: str) -> None:
        with self._tx() as conn:
            conn.execute("DELETE FROM file_snapshots WHERE file_path = ?", (file_path,))
            conn.execute("DELETE FROM files WHERE file_path = ?", (file_path,))

    def known_files(self) -> set[str]:
        rows = self._conn.execute("SELECT file_path FROM file_snapshots").fetchall()
        return {row["file_path"] for row in rows}

    def import_graph(self) -> dict[str, frozenset[str]]:
        rows = self._conn.execute("SELECT file_path, imports FROM files").fetchall()
        return {row["file_path"]: frozenset(json.loads(row["imports"])) for row in rows}

    # --- episodes ---------------------------------------------------------

    def attach_event(self, episode_id: str, event: Event) -> None:
        """Assign `event` to an episode, creating the open episode on first use."""
        assert event.event_id is not None
        ts = event.timestamp.isoformat()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO episodes (episode_id, timestamp_start, timestamp_end, developer) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (episode_id) DO UPDATE SET "
                "timestamp_end = max(timestamp_end, excluded.timestamp_end)",
                (episode_id, ts, ts, event.developer),
            )
            conn.execute(
                "UPDATE events SET episode_id = ? WHERE event_id = ?", (episode_id, event.event_id)
            )

    def open_episode_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT episode_id FROM episodes WHERE status = 'open' ORDER BY timestamp_start"
        ).fetchall()
        return [row["episode_id"] for row in rows]

    def close_episode(self, episode: ClosedEpisode) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE episodes SET status = 'closed', summary = ?, had_deletion = ?, "
                "had_fail_retry_pass = ?, escalated = ?, agent = ?, intent = ?, "
                "jev_rules = ?, jev_reasons = ?, intervention = ? WHERE episode_id = ?",
                (
                    episode.summary,
                    episode.had_deletion,
                    episode.had_fail_retry_pass,
                    episode.escalated,
                    episode.agent,
                    episode.intent,
                    json.dumps(list(episode.jev_rules)),
                    json.dumps(list(episode.jev_reasons)),
                    episode.intervention,
                    episode.episode_id,
                ),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO episode_files (episode_id, file_path) VALUES (?, ?)",
                [(episode.episode_id, path) for path in episode.files],
            )

    def add_assumptions(self, episode_id: str, statements: Sequence[str]) -> None:
        created_at = utcnow().isoformat()
        with self._tx() as conn:
            conn.executemany(
                "INSERT INTO assumptions (assumption_id, statement, source_episode_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                [(uuid.uuid4().hex, s, episode_id, created_at) for s in statements],
            )

    def escalated_files(self, excluding_episode: str) -> set[str]:
        """Files touched by any earlier escalated episode (Jev rule 1)."""
        rows = self._conn.execute(
            "SELECT DISTINCT ef.file_path FROM episode_files ef "
            "JOIN episodes e ON e.episode_id = ef.episode_id "
            "WHERE e.escalated = 1 AND e.episode_id != ?",
            (excluding_episode,),
        ).fetchall()
        return {row["file_path"] for row in rows}

    def history_for(self, files: Iterable[str], excluding_episode: str) -> list[PriorEpisode]:
        """Earlier escalated episodes that touched any of `files`, oldest first."""
        paths = sorted(set(files))
        if not paths:
            return []
        placeholders = ",".join("?" * len(paths))
        rows = self._conn.execute(
            "SELECT DISTINCT e.episode_id, e.timestamp_start, e.intent, e.summary "
            "FROM episodes e "
            "JOIN episode_files ef ON ef.episode_id = e.episode_id "
            f"WHERE e.escalated = 1 AND e.episode_id != ? AND ef.file_path IN ({placeholders}) "
            "ORDER BY e.timestamp_start",
            (excluding_episode, *paths),
        ).fetchall()
        return [
            PriorEpisode(
                episode_id=row["episode_id"],
                timestamp_start=datetime.fromisoformat(row["timestamp_start"]),
                files=self._episode_files(row["episode_id"]),
                intent=row["intent"],
                summary=row["summary"],
                assumptions=self._assumptions(row["episode_id"]),
            )
            for row in rows
        ]

    def recent_episodes(self, limit: int) -> list[EpisodeRow]:
        rows = self._conn.execute(
            "SELECT * FROM episodes ORDER BY timestamp_start DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._episode_row(row) for row in rows]

    def episodes_since(self, since: datetime | None) -> list[EpisodeRow]:
        """Episodes that started at or after `since` (all when None), oldest first."""
        rows = self._conn.execute(
            "SELECT * FROM episodes WHERE timestamp_start >= ? ORDER BY timestamp_start",
            (since.isoformat() if since else "",),
        ).fetchall()
        return [self._episode_row(row) for row in rows]

    def assumptions_for(self, episode_id: str) -> tuple[tuple[str, Validity], ...]:
        return self._assumptions(episode_id)

    # --- model calls ------------------------------------------------------

    def record_model_call(self, call: ModelCall) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO model_calls "
                "(episode_id, ts, model, input_tokens, output_tokens, cost_usd) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    call.episode_id,
                    call.timestamp.isoformat(),
                    call.model,
                    call.input_tokens,
                    call.output_tokens,
                    call.cost_usd,
                ),
            )

    def model_calls_since(self, since: datetime | None) -> list[ModelCall]:
        rows = self._conn.execute(
            "SELECT * FROM model_calls WHERE ts >= ? ORDER BY ts",
            (since.isoformat() if since else "",),
        ).fetchall()
        return [
            ModelCall(
                episode_id=row["episode_id"],
                timestamp=datetime.fromisoformat(row["ts"]),
                model=row["model"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                cost_usd=row["cost_usd"],
            )
            for row in rows
        ]

    def _episode_row(self, row: sqlite3.Row) -> EpisodeRow:
        return EpisodeRow(
            episode_id=row["episode_id"],
            timestamp_start=datetime.fromisoformat(row["timestamp_start"]),
            timestamp_end=datetime.fromisoformat(row["timestamp_end"]),
            developer=row["developer"],
            status=row["status"],
            escalated=bool(row["escalated"]),
            summary=row["summary"],
            files=self._episode_files(row["episode_id"]),
            agent=row["agent"],
            intent=row["intent"],
            jev_rules=tuple(json.loads(row["jev_rules"] or "[]")),
            jev_reasons=tuple(json.loads(row["jev_reasons"] or "[]")),
            intervention=row["intervention"],
        )

    def _episode_files(self, episode_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            "SELECT file_path FROM episode_files WHERE episode_id = ? ORDER BY file_path",
            (episode_id,),
        ).fetchall()
        return tuple(row["file_path"] for row in rows)

    def _assumptions(self, episode_id: str) -> tuple[tuple[str, Validity], ...]:
        rows = self._conn.execute(
            "SELECT statement, current_validity FROM assumptions "
            "WHERE source_episode_id = ? ORDER BY created_at",
            (episode_id,),
        ).fetchall()
        return tuple((row["statement"], row["current_validity"]) for row in rows)


def new_episode_id() -> str:
    return uuid.uuid4().hex[:12]


def _event_from_row(row: sqlite3.Row) -> Event:
    return Event(
        kind=EventKind(row["kind"]),
        timestamp=datetime.fromisoformat(row["ts"]),
        developer=row["developer"],
        files=tuple(json.loads(row["files"])),
        payload=json.loads(row["payload"]),
        event_id=row["event_id"],
    )
