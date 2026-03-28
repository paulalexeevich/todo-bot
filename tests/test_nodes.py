import pytest
import respx
import httpx

from agent.nodes.hackernews import hackernews_node
from agent.nodes.indiehackers import indiehackers_node


@pytest.fixture
def base_state():
    return {
        "idea_text": "AI recipe generator for dietary restrictions",
        "reddit_sources": [],
        "hn_sources": [],
        "ph_sources": [],
        "ih_sources": [],
        "discovery": None,
    }


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_node_returns_sources(base_state):
    respx.get("https://hn.algolia.com/api/v1/search").mock(return_value=httpx.Response(200, json={
        "hits": [
            {"objectID": "123", "title": "Show HN: Recipe AI", "url": "https://example.com", "story_text": "An AI recipe app"},
            {"objectID": "456", "title": "Ask HN: Dietary apps?", "url": None, "story_text": None},
        ]
    }))

    result = await hackernews_node(base_state)
    sources = result["hn_sources"]
    assert len(sources) == 2
    assert sources[0].platform == "hackernews"
    assert sources[0].title == "Show HN: Recipe AI"
    assert sources[0].url == "https://example.com"


@pytest.mark.asyncio
@respx.mock
async def test_hackernews_node_handles_empty(base_state):
    respx.get("https://hn.algolia.com/api/v1/search").mock(return_value=httpx.Response(200, json={"hits": []}))

    result = await hackernews_node(base_state)
    assert result["hn_sources"] == []


@pytest.mark.asyncio
@respx.mock
async def test_indiehackers_node_returns_sources(base_state):
    html = """
    <html><body>
      <a href="/post/recipe-ai-12345">Recipe AI discussion</a>
      <a href="/post/dietary-apps-67890">Best dietary apps</a>
    </body></html>
    """
    respx.get("https://www.indiehackers.com/search").mock(return_value=httpx.Response(200, text=html))

    result = await indiehackers_node(base_state)
    sources = result["ih_sources"]
    assert len(sources) == 2
    assert sources[0].platform == "indiehackers"
    assert "indiehackers.com" in sources[0].url


@pytest.mark.asyncio
@respx.mock
async def test_indiehackers_node_handles_http_error(base_state):
    respx.get("https://www.indiehackers.com/search").mock(return_value=httpx.Response(503))

    result = await indiehackers_node(base_state)
    assert result["ih_sources"] == []
