import json
import os
import sqlite3
import threading
import time

from .models import Event

_lock = threading.Lock()


class Store:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("PAKKA_DB", ":memory:")
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.executescript(
            """
            create table if not exists events (journey_id text, ts real, body text);
            create table if not exists audit (
                id integer primary key autoincrement, journey_id text, at real,
                blocker text, action text, lang text, message text, policy_ok integer, escalated integer,
                code text
            );
            """
        )

    def add_event(self, journey_id: str, event: Event) -> None:
        with _lock:
            self.db.execute("insert into events values (?, ?, ?)", (journey_id, event.ts, event.model_dump_json()))
            self.db.commit()

    def events(self, journey_id: str) -> list[Event]:
        with _lock:
            rows = self.db.execute("select body from events where journey_id = ? order by ts", (journey_id,)).fetchall()
        return [Event(**json.loads(r[0])) for r in rows]

    def attempts(self, journey_id: str, blocker: str, code: str | None = None) -> int:
        """Earlier interventions for this blocker; with a code, only those for that cause."""
        q, args = "select count(*) from audit where journey_id = ? and blocker = ?", (journey_id, blocker)
        if code is not None:
            q, args = q + " and code = ?", args + (code,)
        with _lock:
            return self.db.execute(q, args).fetchone()[0]

    def log(self, journey_id: str, blocker: str, action: str, lang: str, message: str,
            policy_ok: bool, escalated: bool, code: str | None = None) -> None:
        with _lock:
            self.db.execute(
                "insert into audit (journey_id, at, blocker, action, lang, message, policy_ok, escalated, code) "
                "values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (journey_id, time.time(), blocker, action, lang, message, int(policy_ok), int(escalated), code),
            )
            self.db.commit()

    def audit(self, limit: int = 50) -> list[dict]:
        with _lock:
            cur = self.db.execute(
                "select journey_id, at, blocker, action, lang, message, policy_ok, escalated, code "
                "from audit order by id desc limit ?", (limit,)
            )
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
