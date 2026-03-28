import asyncio

import praw

from agent.state import DiscoveryState
from config import settings
from db.models import Source


def _search_reddit_sync(idea_text: str) -> list[Source]:
    if not settings.reddit_client_id:
        return []

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )

    sources: list[Source] = []
    for submission in reddit.subreddit("all").search(idea_text, time_filter="year", limit=10):
        sources.append(Source(
            platform="reddit",
            title=submission.title,
            url=f"https://reddit.com{submission.permalink}",
            snippet=submission.selftext[:300] if submission.selftext else submission.title,
        ))
    return sources


async def reddit_node(state: DiscoveryState) -> dict:  # noqa: F821
    sources = await asyncio.to_thread(_search_reddit_sync, state["idea_text"])
    return {"reddit_sources": sources}
