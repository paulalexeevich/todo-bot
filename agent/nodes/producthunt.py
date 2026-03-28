import httpx

from config import settings
from db.models import Source

_PH_GRAPHQL = "https://api.producthunt.com/v2/api/graphql"

_QUERY = """
query SearchPosts($query: String!) {
  posts(first: 10, order: VOTES, search: { query: $query }) {
    edges {
      node {
        name
        tagline
        url
        description
      }
    }
  }
}
"""


async def producthunt_node(state) -> dict:
    if not settings.product_hunt_token:
        return {"ph_sources": []}

    idea_text: str = state["idea_text"]
    sources: list[Source] = []

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _PH_GRAPHQL,
            json={"query": _QUERY, "variables": {"query": idea_text}},
            headers={"Authorization": f"Bearer {settings.product_hunt_token}"},
        )
        resp.raise_for_status()
        edges = resp.json().get("data", {}).get("posts", {}).get("edges", [])

    for edge in edges:
        node = edge.get("node", {})
        sources.append(Source(
            platform="producthunt",
            title=node.get("name", ""),
            url=node.get("url", ""),
            snippet=node.get("tagline", "") or node.get("description", "")[:300],
        ))

    return {"ph_sources": sources}
