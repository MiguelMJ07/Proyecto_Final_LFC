"""Saved sessions (grammars and SDDs) in a small SQLite file (standard library only).
There is no user system: it is meant for one person or one classroom machine, not for the public internet."""
import json
import os
import sqlite3
from datetime import datetime, timezone

KINDS = ("grammar", "sdd")
MAX_SESSIONS = 200
MAX_PAYLOAD_BYTES = 100_000
MAX_NAME = 60


class SessionError(ValueError):
    pass


class SessionStore:
    def __init__(self, path):
        self.path = path

    def _conn(self):
        d = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(d, exist_ok=True)
        c = sqlite3.connect(self.path, timeout=5)
        c.row_factory = sqlite3.Row
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL, payload TEXT NOT NULL,
            updated TEXT NOT NULL, UNIQUE(kind, name))""")
        return c

    @staticmethod
    def _row(r, with_payload=False):
        d = {"id": r["id"], "kind": r["kind"], "name": r["name"], "updated": r["updated"]}
        if with_payload:
            d["payload"] = json.loads(r["payload"])
        return d

    def list(self, kind=None):
        if kind is not None and kind not in KINDS:
            raise SessionError(f"'kind' must be one of {', '.join(KINDS)}.")
        with self._conn() as c:
            rows = c.execute("SELECT * FROM sessions" + (" WHERE kind = ?" if kind else "") + " ORDER BY updated DESC",
                             (kind,) if kind else ()).fetchall()
        return [self._row(r) for r in rows]

    def get(self, sid):
        with self._conn() as c:
            r = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        if r is None:
            raise KeyError(sid)
        return self._row(r, True)

    def save(self, kind, name, payload):
        if kind not in KINDS:
            raise SessionError(f"'kind' must be one of {', '.join(KINDS)}.")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME:
            raise SessionError(f"'name' must be a non-empty string of at most {MAX_NAME} characters.")
        if not isinstance(payload, dict):
            raise SessionError("'payload' must be an object.")
        text = json.dumps(payload, ensure_ascii=False)
        if len(text.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise SessionError(f"'payload' is larger than {MAX_PAYLOAD_BYTES // 1000} KB.")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as c:
            exists = c.execute("SELECT id FROM sessions WHERE kind = ? AND name = ?", (kind, name.strip())).fetchone()
            if not exists and c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] >= MAX_SESSIONS:
                raise SessionError(f"The store is full ({MAX_SESSIONS} sessions). Delete one first.")
            c.execute("""INSERT INTO sessions (kind, name, payload, updated) VALUES (?, ?, ?, ?)
                         ON CONFLICT(kind, name) DO UPDATE SET payload = excluded.payload, updated = excluded.updated""",
                      (kind, name.strip(), text, now))
            r = c.execute("SELECT * FROM sessions WHERE kind = ? AND name = ?", (kind, name.strip())).fetchone()
        return self._row(r)

    def delete(self, sid):
        with self._conn() as c:
            n = c.execute("DELETE FROM sessions WHERE id = ?", (sid,)).rowcount
        if not n:
            raise KeyError(sid)
