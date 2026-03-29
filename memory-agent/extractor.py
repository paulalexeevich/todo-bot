"""
LLM-based knowledge graph extractor (provider-agnostic via LangChain).
Three extraction modes for the three memory tiers:
  - extract_graph()     Tier 1 — per exchange, immediate facts
  - extract_session()   Tier 2 — session patterns
  - reflect_on_graph()  Tier 3 — daily consolidation
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_EXCHANGE_PROMPT = """You are analyzing a Telegram exchange between a user and their personal assistant bot.
Extract entities and relationships that reveal something lasting about the user: people they know, preferences, recurring events, commitments.

Conversation:
{messages}

Return a JSON object with this exact structure:
{{
  "nodes": [
    {{
      "id": "unique_snake_case_id",
      "type": "Person | Preference | RecurringEvent | Place | Topic",
      "name": "Human-readable name",
      "attributes": {{}}
    }}
  ],
  "edges": [
    {{
      "from_id": "node_id",
      "to_id": "node_id",
      "relation": "KNOWS | HAS_PREFERENCE | ATTENDS | LOCATED_AT | INTERESTED_IN",
      "attributes": {{}}
    }}
  ]
}}

Rules:
- Always add a "user" node (id="user", type="Person", name="User") when the user is the subject.
- Only extract facts explicitly stated — do not infer.
- Use stable IDs: "olga" not "olga_123", "product_meeting" not "meeting_1".
- If nothing significant is learned, return {{"nodes": [], "edges": []}}.
- Return only valid JSON, no markdown, no explanation."""

_SESSION_PROMPT = """You are reviewing a complete conversation session between a user and their personal assistant bot.
Your goal is to find patterns and preferences revealed across the whole session — things not visible in a single exchange.

Full session:
{messages}

Look for:
- Recurring themes or topics the user cares about
- Time patterns (does the user work late? prefer mornings?)
- Implied routines (buys coffee on Mondays, calls Olga on weekends)
- Clusters of related tasks suggesting an ongoing project

Return the same JSON structure:
{{
  "nodes": [...],
  "edges": [...]
}}

Only include patterns clearly supported by the session. Return {{"nodes": [], "edges": []}} if nothing new."""

_REFLECTION_PROMPT = """You are the curator of a personal knowledge graph for a user's assistant bot.
Review the current graph and recent activity to improve its quality.

Current knowledge graph:
{graph_summary}

Recent conversations ({message_count} exchanges):
{recent_messages}

Your tasks:
1. Find duplicate entities to merge (e.g., "Olga" and "wife Olga" are the same person)
2. Identify new recurring patterns not yet captured
3. Flag stale or likely-incorrect nodes for removal

Return JSON with this exact structure:
{{
  "merge": [
    {{
      "keep_id": "olga",
      "remove_ids": ["wife_olga", "olga_wife"],
      "merged_attributes": {{"notes": "user's wife", "relation_to_user": "wife"}}
    }}
  ],
  "add": {{
    "nodes": [...],
    "edges": [...]
  }},
  "remove_ids": ["stale_node_id"]
}}

Return {{"merge": [], "add": {{"nodes": [], "edges": []}}, "remove_ids": []}} if the graph looks clean."""


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _get_llm():
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    if provider == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", api_key=os.environ.get("OPENAI_API_KEY", ""))
    else:  # gemini
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.environ.get("GOOGLE_GEMINI_API_KEY", ""),
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_json(content) -> dict:
    if isinstance(content, list):
        content = "".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


async def _call_llm(prompt: str) -> dict:
    from langchain_core.messages import HumanMessage
    llm = _get_llm()
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return _parse_json(response.content)


# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------

async def extract_graph(messages: list[dict]) -> dict:
    """
    Tier 1 — per-exchange extraction.
    Extracts explicit facts from a batch of recent messages.
    """
    if not messages:
        return {"nodes": [], "edges": []}
    conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
    try:
        return await _call_llm(_EXCHANGE_PROMPT.format(messages=conversation))
    except Exception as e:
        logger.warning("Tier 1 extraction failed: %s", e)
        return {"nodes": [], "edges": []}


async def extract_single_fact(fact: str) -> dict:
    """Extract graph data from a single plaintext fact (used by save_memory MCP tool)."""
    return await extract_graph([{"role": "user", "content": fact}])


async def extract_session(messages: list[dict]) -> dict:
    """
    Tier 2 — session-level extraction.
    Finds patterns across a full conversation that aren't visible per-exchange.
    """
    if not messages:
        return {"nodes": [], "edges": []}
    conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
    try:
        return await _call_llm(_SESSION_PROMPT.format(messages=conversation))
    except Exception as e:
        logger.warning("Tier 2 session extraction failed: %s", e)
        return {"nodes": [], "edges": []}


async def reflect_on_graph(graph_summary: str, recent_messages: list[dict]) -> dict:
    """
    Tier 3 — daily reflection.
    Merges duplicates, identifies new patterns, prunes stale nodes.
    """
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent_messages
    )
    prompt = _REFLECTION_PROMPT.format(
        graph_summary=graph_summary or "(empty graph)",
        message_count=len(recent_messages),
        recent_messages=conversation or "(none)",
    )
    try:
        return await _call_llm(prompt)
    except Exception as e:
        logger.warning("Tier 3 reflection failed: %s", e)
        return {"merge": [], "add": {"nodes": [], "edges": []}, "remove_ids": []}
