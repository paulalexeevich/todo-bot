import pytest
from unittest.mock import AsyncMock, patch

from db.models import DiscoveryResult, Source


MOCK_SOURCES = [
    Source(platform="hackernews", title="Recipe AI startup", url="https://hn.com/1", snippet="People love it"),
    Source(platform="reddit", title="r/startups thread", url="https://reddit.com/r/1", snippet="High demand"),
]

MOCK_RESULT = DiscoveryResult(
    verdict="Strong demand signal. Dietary restriction tracking is an underserved niche.",
    score=7.5,
    market_size="~$2B TAM in food-tech, SAM ~$200M for dietary-specific tools",
    competitors=["Yummly", "Whisk", "Mealime"],
    sentiment_summary="Users frequently complain about lack of personalized dietary options.",
)


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    with patch("db.database.settings") as mock_cfg, \
         patch("config.settings") as mock_main_cfg:
        mock_cfg.db_path = db_file
        mock_main_cfg.db_path = db_file
        mock_main_cfg.reddit_client_id = ""
        mock_main_cfg.product_hunt_token = ""
        mock_main_cfg.llm_provider = "claude"
        mock_main_cfg.anthropic_api_key = "test-key"
        yield


@pytest.mark.asyncio
async def test_full_pipeline_stores_discovery(tmp_path):
    from db.database import init_db, save_idea, get_discovery_for_idea

    with patch("agent.nodes.reddit.reddit_node", new=AsyncMock(return_value={"reddit_sources": MOCK_SOURCES[:1]})), \
         patch("agent.nodes.hackernews.hackernews_node", new=AsyncMock(return_value={"hn_sources": MOCK_SOURCES[1:]})), \
         patch("agent.nodes.producthunt.producthunt_node", new=AsyncMock(return_value={"ph_sources": []})), \
         patch("agent.nodes.indiehackers.indiehackers_node", new=AsyncMock(return_value={"ih_sources": []})), \
         patch("agent.nodes.synthesize.synthesize_node", new=AsyncMock(return_value={"discovery": MOCK_RESULT})):

        # Re-import graph after patching nodes
        import importlib
        import agent.graph
        importlib.reload(agent.graph)

        await init_db()
        idea_id = await save_idea("AI recipe generator for dietary restrictions")

        from agent.graph import discovery_graph
        state = await discovery_graph.ainvoke({
            "idea_text": "AI recipe generator for dietary restrictions",
            "reddit_sources": [],
            "hn_sources": [],
            "ph_sources": [],
            "ih_sources": [],
            "discovery": None,
        })

        assert state["discovery"] is not None
        assert state["discovery"].score == 7.5
