import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from agent.classifier import classify_task
from bot.integrations.github import save_to_github
from config import settings
from db.client import create_task, set_task_type

logger = logging.getLogger(__name__)

_TYPE_EMOJI = {
    "idea": "💡",
    "todo": "📋",
    "note": "📝",
    "learning": "🧠",
    "architecture": "🏗️",
    "question": "❓",
}

_DISCOVERY_TYPES = {"idea"}
_GITHUB_TYPES = {"architecture", "learning"}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != settings.telegram_user_id:
        return

    text = update.message.text.strip()
    if not text:
        return

    # Save immediately with default type, reply at once
    task_id = await create_task(text, type="note")
    await update.message.reply_text(f"Task #{task_id} saved ✓")

    # Classify in background — no await
    asyncio.create_task(_classify_and_followup(task_id, text, update))


async def _classify_and_followup(task_id: int, text: str, update: Update) -> None:
    try:
        classification = await classify_task(text)
        await set_task_type(task_id, classification.type)

        emoji = _TYPE_EMOJI.get(classification.type, "•")
        lines = [f"→ {emoji} *{classification.type}*"]

        if classification.type in _DISCOVERY_TYPES:
            lines.append(f"Discovery runs tonight at {settings.discovery_hour:02d}:{settings.discovery_minute:02d} UTC.")

        if classification.type in _GITHUB_TYPES:
            github_url = await save_to_github(
                task_id=task_id,
                task_type=classification.type,
                title=classification.title,
                body=text,
            )
            if github_url:
                lines.append(f"[Saved to GitHub]({github_url})")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.warning("Background classification failed for task #%d: %s", task_id, e)
