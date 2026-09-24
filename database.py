import sqlite3
from datetime import datetime, timezone

from config import DB_PATH
from models import Giveaway


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute('''CREATE TABLE IF NOT EXISTS subscribers(
        chat_id INTEGER PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS seen(
        source TEXT NOT NULL,
        item_id TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,
        PRIMARY KEY(source, item_id)
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS claims(
        chat_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        item_id TEXT NOT NULL,
        title TEXT NOT NULL,
        claimed_at TEXT NOT NULL,
        PRIMARY KEY(chat_id, source, item_id)
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS reminders(
        chat_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        item_id TEXT NOT NULL,
        reminder_type TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        PRIMARY KEY(chat_id, source, item_id, reminder_type)
    )''')
    con.commit()
    return con


def subscribe(chat_id: int) -> None:
    with db() as con:
        con.execute(
            '''INSERT INTO subscribers(chat_id, enabled, created_at) VALUES (?,1,?)
               ON CONFLICT(chat_id) DO UPDATE SET enabled=1''',
            (chat_id, datetime.now(timezone.utc).isoformat()),
        )
        con.commit()


def set_enabled(chat_id: int, enabled: bool) -> None:
    with db() as con:
        con.execute(
            '''INSERT INTO subscribers(chat_id, enabled, created_at) VALUES (?,?,?)
               ON CONFLICT(chat_id) DO UPDATE SET enabled=excluded.enabled''',
            (chat_id, int(enabled), datetime.now(timezone.utc).isoformat()),
        )
        con.commit()


def subscribers() -> list[int]:
    with db() as con:
        return [int(r['chat_id']) for r in con.execute(
            'SELECT chat_id FROM subscribers WHERE enabled=1'
        )]


def is_seen(g: Giveaway) -> bool:
    with db() as con:
        return con.execute(
            'SELECT 1 FROM seen WHERE source=? AND item_id=?', g.key
        ).fetchone() is not None


def mark_seen(g: Giveaway) -> None:
    with db() as con:
        con.execute(
            'INSERT OR IGNORE INTO seen(source,item_id,first_seen_at) VALUES(?,?,?)',
            (*g.key, datetime.now(timezone.utc).isoformat()),
        )
        con.commit()


def mark_claimed(chat_id: int, g: Giveaway) -> None:
    with db() as con:
        con.execute(
            '''INSERT INTO claims(chat_id,source,item_id,title,claimed_at) VALUES(?,?,?,?,?)
               ON CONFLICT(chat_id,source,item_id)
               DO UPDATE SET title=excluded.title, claimed_at=excluded.claimed_at''',
            (chat_id, g.source, g.item_id, g.title, datetime.now(timezone.utc).isoformat()),
        )
        con.commit()


def is_claimed(chat_id: int, g: Giveaway) -> bool:
    with db() as con:
        return con.execute(
            'SELECT 1 FROM claims WHERE chat_id=? AND source=? AND item_id=?',
            (chat_id, g.source, g.item_id),
        ).fetchone() is not None


def claimed_rows(chat_id: int) -> list[sqlite3.Row]:
    with db() as con:
        return list(con.execute(
            '''SELECT source,item_id,title,claimed_at FROM claims
               WHERE chat_id=? ORDER BY claimed_at DESC''',
            (chat_id,),
        ))


def reminder_sent(chat_id: int, g: Giveaway, kind: str) -> bool:
    with db() as con:
        return con.execute(
            '''SELECT 1 FROM reminders
               WHERE chat_id=? AND source=? AND item_id=? AND reminder_type=?''',
            (chat_id, g.source, g.item_id, kind),
        ).fetchone() is not None


def mark_reminder_sent(chat_id: int, g: Giveaway, kind: str) -> None:
    with db() as con:
        con.execute(
            '''INSERT OR IGNORE INTO reminders(chat_id,source,item_id,reminder_type,sent_at)
               VALUES(?,?,?,?,?)''',
            (chat_id, g.source, g.item_id, kind, datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
