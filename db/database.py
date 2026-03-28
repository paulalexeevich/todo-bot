import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

import aiosqlite

from config import settings
from db.models import Discovery, Idea


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ideas (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                text       TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status     TEXT DEFAULT 'pending'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discoveries (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id        INTEGER NOT NULL REFERENCES ideas(id),
                ran_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reddit_summary TEXT,
                hn_summary     TEXT,
                ph_summary     TEXT,
                ih_summary     TEXT,
                verdict        TEXT,
                score          REAL,
                market_size    TEXT,
                full_report    TEXT
            )
        """)
        await db.commit()


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


async def save_idea(text: str) -> int:
    async with get_db() as db:
        cursor = await db.execute("INSERT INTO ideas (text) VALUES (?)", (text,))
        await db.commit()
        return cursor.lastrowid


async def get_pending_ideas() -> list[Idea]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, text, created_at, status FROM ideas WHERE status = 'pending'"
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        Idea(id=r["id"], text=r["text"], created_at=datetime.fromisoformat(r["created_at"]), status=r["status"])
        for r in rows
    ]


async def get_recent_ideas(limit: int = 10) -> list[Idea]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, text, created_at, status FROM ideas ORDER BY id DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        Idea(id=r["id"], text=r["text"], created_at=datetime.fromisoformat(r["created_at"]), status=r["status"])
        for r in rows
    ]


async def get_idea_by_id(idea_id: int) -> Idea | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, text, created_at, status FROM ideas WHERE id = ?", (idea_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    return Idea(id=row["id"], text=row["text"], created_at=datetime.fromisoformat(row["created_at"]), status=row["status"])


async def set_idea_status(idea_id: int, status: str) -> None:
    async with get_db() as db:
        await db.execute("UPDATE ideas SET status = ? WHERE id = ?", (status, idea_id))
        await db.commit()


async def save_discovery(
    idea_id: int,
    reddit_summary: str | None,
    hn_summary: str | None,
    ph_summary: str | None,
    ih_summary: str | None,
    verdict: str | None,
    score: float | None,
    market_size: str | None,
    full_report: dict | None,
) -> None:
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO discoveries
                (idea_id, reddit_summary, hn_summary, ph_summary, ih_summary,
                 verdict, score, market_size, full_report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idea_id, reddit_summary, hn_summary, ph_summary, ih_summary,
                verdict, score, market_size,
                json.dumps(full_report) if full_report else None,
            ),
        )
        await db.commit()


async def get_discovery_for_idea(idea_id: int) -> Discovery | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM discoveries WHERE idea_id = ? ORDER BY ran_at DESC LIMIT 1",
            (idea_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    return Discovery(
        id=row["id"],
        idea_id=row["idea_id"],
        ran_at=datetime.fromisoformat(row["ran_at"]),
        reddit_summary=row["reddit_summary"],
        hn_summary=row["hn_summary"],
        ph_summary=row["ph_summary"],
        ih_summary=row["ih_summary"],
        verdict=row["verdict"],
        score=row["score"],
        market_size=row["market_size"],
        full_report=row["full_report"],
    )


async def get_idea_counts() -> dict[str, int]:
    async with get_db() as db:
        async with db.execute(
            "SELECT status, COUNT(*) as cnt FROM ideas GROUP BY status"
        ) as cursor:
            rows = await cursor.fetchall()
    return {r["status"]: r["cnt"] for r in rows}
