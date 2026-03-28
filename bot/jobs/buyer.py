import logging

from telegram import Bot

from agent.buyer_graph import buyer_graph
from config import settings
from db.client import save_offer, set_task_status

logger = logging.getLogger(__name__)


async def run_buyer(task_id: int, task_text: str, bot: Bot) -> None:
    await set_task_status(task_id, "processing")
    try:
        state = await buyer_graph.ainvoke({
            "task_text": task_text,
            "offers": [],
        })
        offers = state.get("offers", [])

        for offer in offers:
            await save_offer(
                task_id=task_id,
                title=offer.title,
                price=offer.price,
                store=offer.store,
                url=offer.url,
                snippet=offer.snippet,
            )

        await set_task_status(task_id, "done")

        if offers:
            lines = [f"Found {len(offers)} offers for *{task_text[:50]}*:\n"]
            for o in offers[:5]:
                price_str = f" — {o.price}" if o.price else ""
                lines.append(f"• [{o.store}{price_str}]({o.url})")
            if len(offers) > 5:
                lines.append(f"_+{len(offers) - 5} more in dashboard_")
            await bot.send_message(
                chat_id=settings.telegram_user_id,
                text="\n".join(lines),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        else:
            await bot.send_message(
                chat_id=settings.telegram_user_id,
                text=f"No offers found for task #{task_id}. Try rephrasing.",
            )

    except Exception as e:
        logger.exception("Buyer agent failed for task #%d: %s", task_id, e)
        await set_task_status(task_id, "error")
        await bot.send_message(
            chat_id=settings.telegram_user_id,
            text=f"Buyer agent failed for task #{task_id}: {e}",
        )
