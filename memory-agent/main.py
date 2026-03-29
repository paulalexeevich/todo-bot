"""
Memory Agent service:
- MCP server at /mcp  (tools: query_memory, save_memory, list_entities)
- Health endpoint at /health
- Background task: polls data-api for unprocessed messages, extracts graph, writes to Neo4j
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI

from extractor import extract_graph, extract_session, reflect_on_graph
from graph_client import GraphClient
from mcp_server import mcp, set_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_API_URL = os.environ.get("DATA_API_URL", "http://data-api:8001")
DATA_API_KEY = os.environ.get("DATA_API_KEY", "")
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "changeme")
POLL_INTERVAL = int(os.environ.get("MEMORY_POLL_INTERVAL", "30"))

_http: httpx.AsyncClient | None = None


def _api() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=DATA_API_URL,
            headers={"X-API-Key": DATA_API_KEY},
            timeout=15.0,
        )
    return _http


async def _poll_and_extract() -> None:
    """Fetch unprocessed messages → extract graph → write to Neo4j → mark processed."""
    try:
        r = await _api().get("/messages/unprocessed", params={"limit": 50})
        r.raise_for_status()
        messages = r.json()
        if not messages:
            return

        logger.info("Processing %d messages into knowledge graph.", len(messages))
        graph_data = await extract_graph(messages)

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        if nodes or edges:
            from mcp_server import _graph
            if _graph:
                await _graph.merge_nodes_and_edges(nodes, edges)
                logger.info("Merged %d nodes, %d edges.", len(nodes), len(edges))

        ids = [m["id"] for m in messages]
        await _api().post("/messages/processed", json={"ids": ids})
    except Exception as e:
        logger.warning("Memory poll cycle failed: %s", e)


async def _polling_loop() -> None:
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        await _poll_and_extract()


@asynccontextmanager
async def lifespan(app: FastAPI):
    graph = GraphClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        await graph.verify_connectivity()
        logger.info("Connected to Neo4j at %s", NEO4J_URI)
    except Exception as e:
        logger.error("Neo4j not reachable at startup: %s", e)

    set_graph(graph)

    poll_task = asyncio.create_task(_polling_loop())
    yield
    poll_task.cancel()
    await graph.close()


app = FastAPI(title="Memory Agent", lifespan=lifespan)

# Mount MCP server — all MCP traffic goes to /mcp
app.mount("/mcp", mcp.streamable_http_app())


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/memory/process-now")
async def process_now():
    """Tier 1 — triggered by bot after each reply. Processes unprocessed messages."""
    await _poll_and_extract()
    return {"ok": True}


@app.post("/memory/process-session")
async def process_session():
    """
    Tier 2 — triggered by idle detection (10 min quiet).
    Fetches last 30 messages and extracts session-level patterns.
    """
    try:
        r = await _api().get("/messages/recent", params={"limit": 30})
        r.raise_for_status()
        messages = r.json()
        if not messages:
            return {"ok": True, "extracted": False}

        logger.info("Tier 2 session extraction on %d messages.", len(messages))
        graph_data = await extract_session(messages)

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        if nodes or edges:
            from mcp_server import _graph as g
            if g:
                await g.merge_nodes_and_edges(nodes, edges)
                logger.info("Tier 2: merged %d nodes, %d edges.", len(nodes), len(edges))

        return {"ok": True, "nodes": len(nodes), "edges": len(edges)}
    except Exception as e:
        logger.warning("Tier 2 session extraction failed: %s", e)
        return {"ok": False, "error": str(e)}


@app.post("/memory/reflect")
async def reflect():
    """
    Tier 3 — triggered daily at 03:00 UTC.
    Reviews full graph + recent messages to merge duplicates, find patterns, prune stale nodes.
    """
    try:
        from mcp_server import _graph as g
        if not g:
            return {"ok": False, "error": "Graph not initialized"}

        # Fetch current graph state and recent messages in parallel
        import asyncio as _asyncio
        graph_summary, messages_resp = await _asyncio.gather(
            g.get_graph_summary(),
            _api().get("/messages/recent", params={"limit": 100}),
        )
        messages_resp.raise_for_status()
        recent_messages = messages_resp.json()

        logger.info(
            "Tier 3 reflection: %d chars of graph, %d messages.",
            len(graph_summary), len(recent_messages),
        )

        plan = await reflect_on_graph(graph_summary, recent_messages)

        # Apply merges
        for merge in plan.get("merge", []):
            await g.merge_duplicate_nodes(
                merge["keep_id"], merge.get("remove_ids", []), merge.get("merged_attributes", {})
            )

        # Add new nodes/edges
        add = plan.get("add", {})
        if add.get("nodes") or add.get("edges"):
            await g.merge_nodes_and_edges(add.get("nodes", []), add.get("edges", []))

        # Remove stale nodes
        remove_ids = plan.get("remove_ids", [])
        if remove_ids:
            await g.delete_nodes(remove_ids)

        logger.info(
            "Tier 3 done: %d merges, %d additions, %d removals.",
            len(plan.get("merge", [])),
            len(add.get("nodes", [])) + len(add.get("edges", [])),
            len(remove_ids),
        )
        return {"ok": True, "plan": plan}
    except Exception as e:
        logger.warning("Tier 3 reflection failed: %s", e)
        return {"ok": False, "error": str(e)}
