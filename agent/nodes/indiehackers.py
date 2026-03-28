import httpx
from bs4 import BeautifulSoup

from db.models import Source

_IH_SEARCH = "https://www.indiehackers.com/search"


async def indiehackers_node(state) -> dict:
    idea_text: str = state["idea_text"]
    sources: list[Source] = []

    headers = {"User-Agent": "Mozilla/5.0 (compatible; idea-bot/1.0)"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        try:
            resp = await client.get(_IH_SEARCH, params={"query": idea_text}, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError:
            return {"ih_sources": []}

    soup = BeautifulSoup(resp.text, "lxml")

    # IH search results are rendered server-side as article/post links
    for link in soup.select("a[href*='/post/']")[:10]:
        title = link.get_text(strip=True)
        href = link.get("href", "")
        url = href if href.startswith("http") else f"https://www.indiehackers.com{href}"
        if title:
            sources.append(Source(
                platform="indiehackers",
                title=title,
                url=url,
                snippet=title,
            ))

    return {"ih_sources": sources}
