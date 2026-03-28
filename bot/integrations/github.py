"""GitHub API integration — saves architecture and learning notes as markdown files."""
import base64
import logging
from datetime import datetime, timezone

import httpx

from config import settings

logger = logging.getLogger(__name__)

KNOWLEDGE_PATHS = {
    "architecture": "knowledge/architecture",
    "learning": "knowledge/learnings",
}


async def save_to_github(task_id: int, task_type: str, title: str, body: str) -> str | None:
    """
    Creates a markdown file in the GitHub knowledge repo.
    Returns the file URL on success, None on failure or if GitHub is not configured.
    """
    if not settings.github_token or not settings.github_repo:
        return None

    folder = KNOWLEDGE_PATHS.get(task_type)
    if not folder:
        return None

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    path = f"{folder}/{date_str}-{slug}.md"

    content = f"# {title}\n\n> Task #{task_id} — saved {date_str}\n\n{body}\n"
    encoded = base64.b64encode(content.encode()).decode()

    url = f"https://api.github.com/repos/{settings.github_repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        # Check if file exists (needed for update)
        sha = None
        existing = await client.get(url, headers=headers)
        if existing.status_code == 200:
            sha = existing.json().get("sha")

        payload: dict = {
            "message": f"Add {task_type}: {title[:72]}",
            "content": encoded,
        }
        if sha:
            payload["sha"] = sha

        resp = await client.put(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            html_url = resp.json().get("content", {}).get("html_url", "")
            logger.info("Saved to GitHub: %s", html_url)
            return html_url
        else:
            logger.warning("GitHub save failed: %s %s", resp.status_code, resp.text[:200])
            return None


def _slugify(text: str) -> str:
    import re
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug[:50] or "note"
