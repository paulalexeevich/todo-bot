"""
Memory update jobs — Tier 2 (session idle) and Tier 3 (daily reflection).
Tier 1 (per-exchange) is triggered directly from the message handler.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from config import settings
from db.client import get_setting, set_setting

logger = logging.getLogger(__name__)

_SESSION_IDLE_SECONDS = 600  # 10 minutes


async def _call_memory(endpoint: str, timeout: float = 30.0) -> None:
    memory_url = settings.memory_agent_url
    if not memory_url:
        return
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{memory_url}{endpoint}")
            r.raise_for_status()
    except Exception as e:
        logger.warning("Memory agent %s failed: %s", endpoint, e)


async def check_session_idle(context) -> None:
    """
    Tier 2 — runs every 60s.
    When the user goes quiet for 10+ minutes, trigger a session-level extraction
    that looks at the full recent conversation for patterns (not just individual exchanges).
    """
    last_msg = await get_setting("last_user_message_at")
    if not last_msg:
        return

    last_msg_dt = datetime.fromisoformat(last_msg)
    now = datetime.now(timezone.utc)

    if (now - last_msg_dt).total_seconds() < _SESSION_IDLE_SECONDS:
        return  # still active

    session_extracted = await get_setting("session_extracted_at")
    if session_extracted:
        if datetime.fromisoformat(session_extracted) >= last_msg_dt:
            return  # already processed this session

    logger.info("Session idle — triggering Tier 2 session extraction.")
    await _call_memory("/memory/process-session")
    await set_setting("session_extracted_at", now.isoformat())


async def daily_reflection(context) -> None:
    """
    Tier 3 — runs once daily at 03:00 UTC.
    Reviews the entire knowledge graph against recent conversations:
    merges duplicates, identifies new patterns, prunes stale nodes.
    """
    logger.info("Running Tier 3 daily memory reflection.")
    await _call_memory("/memory/reflect", timeout=120.0)
