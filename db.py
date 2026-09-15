from __future__ import annotations

import aiosqlite
from config import settings


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_chat_user
ON messages(chat_id, user_id, id);
"""


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(CREATE_SQL)
        await db.commit()


async def add_message(chat_id: int, user_id: int, role: str, content: str) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO messages(chat_id, user_id, role, content) VALUES(?,?,?,?)",
            (chat_id, user_id, role, content),
        )
        await db.commit()


async def get_history(chat_id: int, user_id: int, limit: int | None = None) -> list[dict]:
    limit = limit or settings.max_history_messages
    async with aiosqlite.connect(settings.db_path) as db:
        cursor = await db.execute(
            """
            SELECT role, content
            FROM messages
            WHERE chat_id = ? AND user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, user_id, limit),
        )
        rows = await cursor.fetchall()
    rows.reverse()
    return [{"role": role, "content": content} for role, content in rows]


async def clear_history(chat_id: int, user_id: int) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "DELETE FROM messages WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        await db.commit()
