import httpx

from db.models import Source

_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


async def hackernews_node(state) -> dict:
    idea_text: str = state["idea_text"]
    sources: list[Source] = []

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(_ALGOLIA_URL, params={
            "query": idea_text,
            "tags": "story",
            "hitsPerPage": 10,
        })
        resp.raise_for_status()
        hits = resp.json().get("hits", [])

    for hit in hits:
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        sources.append(Source(
            platform="hackernews",
            title=hit.get("title", ""),
            url=url,
            snippet=hit.get("story_text", "")[:300] if hit.get("story_text") else hit.get("title", ""),
        ))

    return {"hn_sources": sources}
