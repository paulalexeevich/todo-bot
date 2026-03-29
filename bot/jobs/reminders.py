"""Periodic job: check for due reminders and send Telegram notifications."""
import logging
from datetime import datetime, timezone

from telegram.ext import ContextTypes

from config import settings
from db.client import get_due_reminders, mark_task_notified

logger = logging.getLogger(__name__)


async def check_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    try:
        due = await get_due_reminders(now_iso)
    except Exception as e:
        logger.warning("Failed to fetch due reminders: %s", e)
        return

    for task in due:
        task_id = task["id"]
        title = task.get("text", "")[:80]
        due_date = task.get("due_date", "")
        due_time = task.get("due_time", "")
        try:
            await context.bot.send_message(
                chat_id=settings.telegram_user_id,
                text=f"⏰ Reminder #{task_id}: {title}\nScheduled: {due_date} {due_time} UTC",
            )
            await mark_task_notified(task_id)
            logger.info("Reminder #%d notified.", task_id)
        except Exception as e:
            logger.warning("Failed to notify reminder #%d: %s", task_id, e)
