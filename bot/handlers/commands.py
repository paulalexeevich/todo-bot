import datetime
import json

from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from db.client import get_discovery_for_task, get_recent_tasks, get_task_by_id, get_task_counts

_STATUS_EMOJI = {"pending": "⏳", "processing": "🔄", "done": "✅", "error": "❌"}
_TYPE_EMOJI = {"idea": "💡", "todo": "📋", "note": "📝"}


def _guard(update: Update) -> bool:
    return update.effective_user.id == settings.telegram_user_id


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    tasks = await get_recent_tasks(10)
    if not tasks:
        await update.message.reply_text("No tasks yet. Just send me a message!")
        return
    lines = [
        f"{_STATUS_EMOJI.get(t.status, '?')} {_TYPE_EMOJI.get(t.type, '•')} "
        f"#{t.id} — {t.text[:55]}{'…' if len(t.text) > 55 else ''}"
        for t in tasks
    ]
    await update.message.reply_text("\n".join(lines))


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /report <task_id>")
        return

    task_id = int(args[0])
    task = await get_task_by_id(task_id)
    if not task:
        await update.message.reply_text(f"Task #{task_id} not found.")
        return

    discovery = await get_discovery_for_task(task_id)
    if not discovery:
        await update.message.reply_text(
            f"No discovery yet for task #{task_id} (status: {task.status}).\n"
            "Discovery runs nightly. Use /debug_run to trigger manually."
        )
        return

    score_bar = "█" * round(discovery.score or 0) + "░" * (10 - round(discovery.score or 0))
    competitors = ""
    if discovery.full_report:
        comps = discovery.full_report.get("competitors", []) if isinstance(discovery.full_report, dict) else []
        if comps:
            competitors = "\n\n*Competitors:*\n" + "\n".join(f"• {c}" for c in comps)

    report = (
        f"*Task #{task_id}* [{task.type}]\n{task.text}\n\n"
        f"*Score:* {discovery.score:.1f}/10  [{score_bar}]\n\n"
        f"*Verdict:*\n{discovery.verdict}\n\n"
        f"*Market Size:*\n{discovery.market_size}\n\n"
        f"*Community Sentiment:*\n"
        f"{discovery.ih_summary or discovery.reddit_summary or discovery.hn_summary or 'N/A'}"
        f"{competitors}"
    )
    await update.message.reply_text(report, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    counts = await get_task_counts()
    total = sum(counts.values())
    pending = counts.get("pending", 0)
    done = counts.get("done", 0)
    error = counts.get("error", 0)

    now = datetime.datetime.now(datetime.timezone.utc)
    next_run = now.replace(
        hour=settings.discovery_hour,
        minute=settings.discovery_minute,
        second=0,
        microsecond=0,
    )
    if next_run <= now:
        next_run += datetime.timedelta(days=1)

    await update.message.reply_text(
        f"Tasks: {total} total | {pending} pending | {done} done | {error} errors\n"
        f"Next discovery run: {next_run.strftime('%Y-%m-%d %H:%M UTC')}"
    )


async def cmd_debug_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    from bot.jobs.discovery import run_discovery
    await update.message.reply_text("Starting discovery run now...")
    await run_discovery(context)
