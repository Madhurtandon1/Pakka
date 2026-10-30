"""SQLite tables for merchant consent, episodes, routed lender requests and the merchant audit log."""
import json
import os
import sqlite3
import threading
import uuid
from datetime import date, datetime
from typing import Optional

from .models import DISTRESS, ConsentIn, ConsentRecord

_lock = threading.Lock()

SCHEMA = """
create table if not exists merchant_consent (
    id integer primary key autoincrement, merchant_id text, notice_version text, language text,
    early_warning_alerts integer, soundbox_cue integer, repeat_offers integer,
    granted_at text, withdrawn_at text, channel text, window_start integer, window_end integer
);
create table if not exists merchant_episodes (
    episode_id text primary key, merchant_id text, loan_id text, opened_day text,
    closed_day text, stopped integer default 0
);
create table if not exists merchant_requests (
    request_id text primary key, merchant_id text, loan_id text, lender_id text, kind text,
    note text, status text, created_at text
);
create table if not exists merchant_audit (
    id integer primary key autoincrement, ts text, merchant_id text, loan_id text, episode_id text,
    blocker text, rule_ids text, intent text, intent_source text, action text, template_id text,
    channel text, consent_version text, guard_blocks text, policy_ok integer, escalated integer,
    lender_request_id text, scheduled_for text, language text, proactive integer,
    oldest_unpaid text, message text
);
create table if not exists merchant_sim (merchant_id text primary key, day integer);
"""

TABLES = ["merchant_consent", "merchant_episodes", "merchant_requests", "merchant_audit", "merchant_sim"]


class MerchantStore:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("PAKKA_DB", ":memory:")
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def _write(self, sql: str, args: tuple = ()) -> None:
        with _lock:
            self.db.execute(sql, args)
            self.db.commit()

    def reset(self) -> None:
        with _lock:
            for t in TABLES:
                self.db.execute(f"delete from {t}")
            self.db.commit()

    # Consent: every grant is a new versioned row; withdrawing stamps the active one.
    def grant_consent(self, merchant_id: str, body: ConsentIn, at: datetime) -> ConsentRecord:
        self.withdraw_consent(merchant_id, at)
        self._write(
            "insert into merchant_consent (merchant_id, notice_version, language, early_warning_alerts, "
            "soundbox_cue, repeat_offers, granted_at, channel, window_start, window_end) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (merchant_id, body.notice_version, body.language, int(body.early_warning_alerts),
             int(body.soundbox_cue), int(body.repeat_offers), at.isoformat(), body.channel,
             *(body.contact_window or (None, None))))
        return self.consent(merchant_id)

    def withdraw_consent(self, merchant_id: str, at: datetime) -> bool:
        active = self.db.execute(
            "select count(*) from merchant_consent where merchant_id = ? and withdrawn_at is null",
            (merchant_id,)).fetchone()[0]
        self._write("update merchant_consent set withdrawn_at = ? where merchant_id = ? and withdrawn_at is null",
                    (at.isoformat(), merchant_id))
        return bool(active)

    def consent(self, merchant_id: str) -> Optional[ConsentRecord]:
        r = self.db.execute("select * from merchant_consent where merchant_id = ? order by id desc limit 1",
                            (merchant_id,)).fetchone()
        if not r:
            return None
        return ConsentRecord(
            merchant_id=r["merchant_id"], notice_version=r["notice_version"], language=r["language"],
            early_warning_alerts=bool(r["early_warning_alerts"]), soundbox_cue=bool(r["soundbox_cue"]),
            repeat_offers=bool(r["repeat_offers"]), granted_at=r["granted_at"],
            withdrawn_at=r["withdrawn_at"], channel=r["channel"],
            contact_window=(r["window_start"], r["window_end"]) if r["window_start"] is not None else None)

    def consent_history(self, merchant_id: str) -> list[dict]:
        rows = self.db.execute("select * from merchant_consent where merchant_id = ? order by id", (merchant_id,))
        return [dict(r) for r in rows]

    # Episodes run from the first shortfall until cured.
    def open_episode(self, merchant_id: str) -> Optional[dict]:
        r = self.db.execute("select * from merchant_episodes where merchant_id = ? and closed_day is null",
                            (merchant_id,)).fetchone()
        return dict(r) if r else None

    def start_episode(self, merchant_id: str, loan_id: str, day: date) -> dict:
        eid = f"E-{merchant_id}-{day:%m%d}"
        self._write("insert or ignore into merchant_episodes (episode_id, merchant_id, loan_id, opened_day) "
                    "values (?, ?, ?, ?)", (eid, merchant_id, loan_id, day.isoformat()))
        self._write("update merchant_episodes set closed_day = null where episode_id = ?", (eid,))
        return self.open_episode(merchant_id)

    def close_episode(self, episode_id: str, day: date) -> None:
        self._write("update merchant_episodes set closed_day = ? where episode_id = ?", (day.isoformat(), episode_id))

    def stop_episode(self, episode_id: str) -> None:
        self._write("update merchant_episodes set stopped = 1 where episode_id = ?", (episode_id,))

    def episodes(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("select * from merchant_episodes")]

    # Contact history, read back from the audit log.
    def attempts(self, episode_id: str) -> int:
        return self.db.execute(
            "select count(*) from merchant_audit where episode_id = ? and proactive = 1 and channel != 'none'",
            (episode_id,)).fetchone()[0]

    def contacts_on(self, merchant_id: str, day: date) -> int:
        return self.db.execute(
            "select count(*) from merchant_audit where merchant_id = ? and proactive = 1 and channel != 'none' "
            "and substr(ts, 1, 10) = ?", (merchant_id, day.isoformat())).fetchone()[0]

    def last_contact_day(self, episode_id: str) -> Optional[date]:
        r = self.db.execute(
            "select max(ts) from merchant_audit where episode_id = ? and proactive = 1 and channel != 'none' "
            "and blocker = 'edi_shortfall'", (episode_id,)).fetchone()[0]
        return date.fromisoformat(r[:10]) if r else None

    def contacted_oldest(self, episode_id: str) -> set[date]:
        rows = self.db.execute(
            "select distinct oldest_unpaid from merchant_audit where episode_id = ? and proactive = 1 "
            "and channel != 'none' and oldest_unpaid is not null", (episode_id,))
        return {date.fromisoformat(r[0]) for r in rows}

    def last_dip_nudge(self, merchant_id: str) -> Optional[date]:
        r = self.db.execute("select max(ts) from merchant_audit where merchant_id = ? "
                            "and blocker = 'sales_dip_risk' and channel != 'none'", (merchant_id,)).fetchone()[0]
        return date.fromisoformat(r[:10]) if r else None

    def last_stress(self, merchant_id: str) -> Optional[date]:
        marks = ", ".join("?" * len(DISTRESS))
        r = self.db.execute(
            f"select max(ts) from merchant_audit where merchant_id = ? and "
            f"(intent in ({marks}) or action = 'human_handoff')",
            (merchant_id, *sorted(DISTRESS))).fetchone()[0]
        return date.fromisoformat(r[:10]) if r else None

    # Lender requests: Pakka only routes them; the lender decides.
    def add_request(self, merchant_id: str, loan_id: str, lender_id: str, kind: str, note: str,
                    at: datetime) -> str:
        rid = "REQ-" + uuid.uuid4().hex[:8].upper()
        status = "pending_lender_contact" if kind == "human_handoff" else "pending_lender_decision"
        self._write("insert into merchant_requests values (?, ?, ?, ?, ?, ?, ?, ?)",
                    (rid, merchant_id, loan_id, lender_id, kind, note, status, at.isoformat()))
        return rid

    def requests(self, lender_id: str | None = None) -> list[dict]:
        q, args = "select * from merchant_requests", ()
        if lender_id:
            q, args = q + " where lender_id = ?", (lender_id,)
        return [dict(r) for r in self.db.execute(q + " order by created_at desc", args)]

    # Audit
    def log(self, row: dict) -> None:
        row = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v) for k, v in row.items()}
        cols = ", ".join(row)
        self._write(f"insert into merchant_audit ({cols}) values ({', '.join('?' * len(row))})",
                    tuple(row.values()))

    def audit(self, limit: int = 100, merchant_id: str | None = None) -> list[dict]:
        q, args = "select * from merchant_audit", ()
        if merchant_id:
            q, args = q + " where merchant_id = ?", (merchant_id,)
        out = []
        for r in self.db.execute(q + " order by id desc limit ?", args + (limit,)).fetchall():
            d = dict(r)
            d["rule_ids"] = json.loads(d["rule_ids"] or "[]")
            d["guard_blocks"] = json.loads(d["guard_blocks"] or "[]")
            out.append(d)
        return out

    def sim_day(self, merchant_id: str) -> int:
        r = self.db.execute("select day from merchant_sim where merchant_id = ?", (merchant_id,)).fetchone()
        return r[0] if r else 1

    def set_sim_day(self, merchant_id: str, day: int) -> None:
        self._write("insert or replace into merchant_sim values (?, ?)", (merchant_id, day))
