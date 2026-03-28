from telegram import Update
from telegram.ext import ContextTypes

from agent.classifier import classify_task
from bot.integrations.github import save_to_github
from config import settings
from db.client import create_task

_TYPE_EMOJI = {
    "idea": "💡",
    "todo": "📋",
    "note": "📝",
    "learning": "🧠",
    "architecture": "🏗️",
    "question": "❓",
}

# Types that queue for the nightly discovery pipeline
_DISCOVERY_TYPES = {"idea"}

# Types that get saved to GitHub knowledge base
_GITHUB_TYPES = {"architecture", "learning"}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != settings.telegram_user_id:
        return

    text = update.message.text.strip()
    if not text:
        return

    # Classify the task
    classification = await classify_task(text)
    emoji = _TYPE_EMOJI.get(classification.type, "•")

    # Save to DB
    task_id = await create_task(text, type=classification.type)

    # Build reply
    lines = [f"Task #{task_id} saved as {emoji} *{classification.type}*"]

    if classification.type in _DISCOVERY_TYPES:
        lines.append(f"Discovery will run tonight at {settings.discovery_hour:02d}:{settings.discovery_minute:02d} UTC.")

    # Save to GitHub for architecture/learning
    if classification.type in _GITHUB_TYPES:
        github_url = await save_to_github(
            task_id=task_id,
            task_type=classification.type,
            title=classification.title,
            body=text,
        )
        if github_url:
            lines.append(f"[Saved to GitHub]({github_url})")
        elif settings.github_token:
            lines.append("_(GitHub save failed)_")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
