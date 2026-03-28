import pytest
from unittest.mock import patch

from db.database import get_idea_counts, get_recent_ideas, save_idea, set_idea_status


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    with patch("db.database.settings") as mock_settings:
        mock_settings.db_path = db_file
        yield


@pytest.mark.asyncio
async def test_save_and_list_idea():
    from db.database import init_db
    await init_db()

    idea_id = await save_idea("AI-powered recipe generator")
    assert isinstance(idea_id, int)
    assert idea_id > 0

    ideas = await get_recent_ideas(10)
    assert len(ideas) == 1
    assert ideas[0].text == "AI-powered recipe generator"
    assert ideas[0].status == "pending"


@pytest.mark.asyncio
async def test_set_idea_status():
    from db.database import init_db
    await init_db()

    idea_id = await save_idea("Some idea")
    await set_idea_status(idea_id, "done")

    ideas = await get_recent_ideas()
    assert ideas[0].status == "done"


@pytest.mark.asyncio
async def test_idea_counts():
    from db.database import init_db
    await init_db()

    await save_idea("Idea 1")
    await save_idea("Idea 2")
    idea_id = (await save_idea("Idea 3"))
    await set_idea_status(idea_id, "done")

    counts = await get_idea_counts()
    assert counts["pending"] == 2
    assert counts["done"] == 1
