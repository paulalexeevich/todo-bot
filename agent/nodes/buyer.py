"""Buyer agent node — searches DuckDuckGo for product offers and returns structured results."""
import asyncio
import logging
import re
from urllib.parse import urlparse

from db.models import Offer

logger = logging.getLogger(__name__)


def _extract_price(text: str) -> str | None:
    """Pull first price-like pattern from snippet text."""
    patterns = [
        r'[\$€£₽¥]\s?\d[\d\s,\.]*',   # symbol first: $29.99, ₽1 500
        r'\d[\d\s,\.]*\s?[\$€£₽¥]',   # symbol last:  29.99$
        r'\d[\d\s,\.]*\s?(?:руб|rub|usd|eur|USD|EUR|RUB)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def _store_name(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host.replace("www.", "")
    except Exception:
        return url


def _search_sync(query: str, max_results: int = 10) -> list[Offer]:
    from duckduckgo_search import DDGS

    offers: list[Offer] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                price = _extract_price(r.get("body", ""))
                offers.append(Offer(
                    title=r["title"],
                    price=price,
                    store=_store_name(r["href"]),
                    url=r["href"],
                    snippet=r.get("body", "")[:200],
                ))
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s", e)
    return offers


async def buyer_node(state: dict) -> dict:
    task_text: str = state["task_text"]

    # Build a focused shopping query
    query = f"{task_text} buy price"
    offers = await asyncio.to_thread(_search_sync, query)

    logger.info("Buyer agent found %d offers for: %s", len(offers), task_text)
    return {"offers": offers}
