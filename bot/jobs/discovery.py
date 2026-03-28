import logging

from telegram.ext import ContextTypes

from agent.graph import discovery_graph
from config import settings
from db.client import get_pending_tasks, save_discovery, set_task_status
from db.models import DiscoveryResult, Source

logger = logging.getLogger(__name__)


async def run_discovery(context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = await get_pending_tasks(type="idea")
    if not tasks:
        logger.info("No pending idea tasks to process.")
        return

    logger.info("Starting discovery for %d task(s).", len(tasks))

    for task in tasks:
        await set_task_status(task.id, "processing")
        try:
            state = await discovery_graph.ainvoke({
                "idea_text": task.text,
                "reddit_sources": [],
                "hn_sources": [],
                "ph_sources": [],
                "ih_sources": [],
                "discovery": None,
            })

            result: DiscoveryResult | None = state.get("discovery")
            all_sources: list[Source] = (
                state.get("reddit_sources", [])
                + state.get("hn_sources", [])
                + state.get("ph_sources", [])
                + state.get("ih_sources", [])
            )
            full_report = {
                "competitors": result.competitors if result else [],
                "sentiment_summary": result.sentiment_summary if result else None,
                "sources": [{"platform": s.platform, "title": s.title, "url": s.url} for s in all_sources],
            }

            await save_discovery(
                task_id=task.id,
                reddit_summary=_summarize(state.get("reddit_sources", [])),
                hn_summary=_summarize(state.get("hn_sources", [])),
                ph_summary=_summarize(state.get("ph_sources", [])),
                ih_summary=_summarize(state.get("ih_sources", [])),
                verdict=result.verdict if result else None,
                score=result.score if result else None,
                market_size=result.market_size if result else None,
                full_report=full_report,
            )
            await set_task_status(task.id, "done")

            score_str = f"{result.score:.1f}/10" if result else "N/A"
            verdict_short = (
                (result.verdict[:120] + "…") if result and len(result.verdict) > 120
                else (result.verdict if result else "N/A")
            )

            await context.bot.send_message(
                chat_id=settings.telegram_user_id,
                text=(
                    f"Discovery complete for task #{task.id}\n"
                    f"Score: {score_str}\n\n"
                    f"{verdict_short}\n\n"
                    f"Use /report {task.id} for the full report."
                ),
            )

        except Exception as exc:
            logger.exception("Discovery failed for task #%d: %s", task.id, exc)
            await set_task_status(task.id, "error")
            await context.bot.send_message(
                chat_id=settings.telegram_user_id,
                text=f"Discovery failed for task #{task.id}: {exc}",
            )


def _summarize(sources: list[Source]) -> str | None:
    if not sources:
        return None
    return "\n".join(f"• {s.title} ({s.url})" for s in sources[:5])
