"""
MCP server for the memory agent.
Exposes three tools that any MCP-compatible client (Claude Code, LangChain, etc.) can call:

  query_memory(query)         — find what's known about entities in the query
  save_memory(fact)           — store a new fact in the knowledge graph
  list_entities(entity_type)  — browse the graph
"""
from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Injected from main.py after Neo4j is ready
_graph = None


def set_graph(graph) -> None:
    global _graph
    _graph = graph


mcp = FastMCP("memory-agent")


@mcp.tool()
async def query_memory(query: str) -> str:
    """
    Search the long-term knowledge graph for facts about entities mentioned in the query.
    Use this before processing a user task to retrieve relevant context:
    people the user knows, preferences, recurring events, commitments.

    Returns a formatted string of facts, or an empty string if nothing is known.
    """
    if not _graph:
        return ""
    try:
        result = await _graph.format_context(query)
        return result or ""
    except Exception as e:
        logger.warning("query_memory failed: %s", e)
        return ""


@mcp.tool()
async def save_memory(fact: str) -> str:
    """
    Save a new fact about the user to the long-term knowledge graph.
    Call this when you learn something lasting: a person's name and relationship,
    a preference, a recurring event, or a commitment.

    Examples:
      "Olga is the user's wife"
      "User prefers morning reminders"
      "Product team meeting every Tuesday at 14:00"
    """
    if not _graph:
        return "Memory unavailable."
    try:
        from extractor import extract_single_fact
        graph_data = await extract_single_fact(fact)
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        if nodes or edges:
            await _graph.merge_nodes_and_edges(nodes, edges)
            return f"Saved ({len(nodes)} entities, {len(edges)} relationships)."
        return "Nothing significant extracted from that fact."
    except Exception as e:
        logger.warning("save_memory failed: %s", e)
        return f"Failed to save: {e}"


@mcp.tool()
async def list_entities(entity_type: str = "") -> str:
    """
    List entities stored in the knowledge graph.
    Optionally filter by type: Person, Preference, RecurringEvent, Place, Topic.
    Returns a formatted list of known entities and their key attributes.
    """
    if not _graph:
        return "Memory unavailable."
    try:
        cypher = (
            "MATCH (n) WHERE n.type = $type RETURN n ORDER BY n.name LIMIT 50"
            if entity_type
            else "MATCH (n) RETURN n ORDER BY n.type, n.name LIMIT 50"
        )
        async with _graph._driver.session() as session:
            result = await session.run(cypher, type=entity_type)
            rows = await result.data()

        if not rows:
            return "No entities found."

        lines: list[str] = []
        for row in rows:
            n = dict(row["n"])
            name = n.get("name", "?")
            ntype = n.get("type", "Entity")
            attrs = {k: v for k, v in n.items() if k not in ("name", "type", "id")}
            line = f"[{ntype}] {name}"
            if attrs:
                line += " — " + ", ".join(f"{k}: {v}" for k, v in attrs.items())
            lines.append(line)
        return "\n".join(lines)
    except Exception as e:
        logger.warning("list_entities failed: %s", e)
        return f"Failed to list entities: {e}"
