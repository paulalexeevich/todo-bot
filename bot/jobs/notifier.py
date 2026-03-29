"""Task completion notification helpers."""
import logging

from telegram import Bot
from telegram.ext import ContextTypes

from config import settings
from db.client import get_newly_done_tasks, mark_completion_notified

logger = logging.getLogger(__name__)

_TYPE_EMOJI = {
    "idea": "💡", "todo": "📋", "note": "📝", "learning": "🧠",
    "architecture": "🏗️", "question": "❓", "shopping": "🛒", "reminder": "⏰",
}


async def notify_task_done(bot: Bot, task_id: int, task_text: str, task_type: str) -> None:
    """Send a Telegram notification when a task is marked done."""
    emoji = _TYPE_EMOJI.get(task_type, "✅")
    short = task_text[:70] + ("…" if len(task_text) > 70 else "")
    try:
        await bot.send_message(
            chat_id=settings.telegram_user_id,
            text=f"✅ Task #{task_id} done {emoji}\n{short}",
        )
    except Exception as e:
        logger.warning("Completion notification failed for task #%d: %s", task_id, e)


async def check_completions(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic job: notify for tasks that became done since last check."""
    try:
        tasks = await get_newly_done_tasks()
    except Exception as e:
        logger.warning("Failed to fetch newly done tasks: %s", e)
        return

    for task in tasks:
        task_id = task["id"]
        try:
            await notify_task_done(context.bot, task_id, task.get("text", ""), task.get("type", ""))
            await mark_completion_notified(task_id)
        except Exception as e:
            logger.warning("Completion notification failed for task #%d: %s", task_id, e)
