import asyncio
import logging

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot.handlers.commands import cmd_debug_run, cmd_list, cmd_report, cmd_status
from bot.handlers.idea import handle_message
from bot.jobs.discovery import run_discovery
from config import settings

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application) -> None:
    # Claim the polling session: delete any existing webhook and flush pending updates.
    # This prevents 409 Conflict when the container restarts.
    await application.bot.delete_webhook(drop_pending_updates=True)
    # Brief pause so Telegram can close any in-flight long-poll from the old instance.
    await asyncio.sleep(2)
    logger.info("Session claimed, starting polling.")


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("debug_run", cmd_debug_run))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_daily(run_discovery, time=settings.discovery_time, name="nightly_discovery")
    logger.info(
        "Nightly discovery scheduled at %02d:%02d UTC.",
        settings.discovery_hour,
        settings.discovery_minute,
    )

    logger.info("Bot starting (long polling)...")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message"])


if __name__ == "__main__":
    main()
