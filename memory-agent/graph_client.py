"""
Neo4j knowledge graph client.
Stores and queries entities + relationships extracted from conversations.
"""
from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


class GraphClient:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self) -> None:
        await self._driver.close()

    async def verify_connectivity(self) -> None:
        await self._driver.verify_connectivity()

    async def merge_nodes_and_edges(self, nodes: list[dict], edges: list[dict]) -> None:
        """
        Upsert graph elements extracted from a conversation.

        nodes: [{"id": str, "type": str, "name": str, "attributes": dict}]
        edges: [{"from_id": str, "to_id": str, "relation": str, "attributes": dict}]
        """
        async with self._driver.session() as session:
            for node in nodes:
                await session.execute_write(
                    _merge_node,
                    node["id"],
                    node.get("type", "Entity"),
                    node.get("name", node["id"]),
                    node.get("attributes", {}),
                )
            for edge in edges:
                await session.execute_write(
                    _merge_edge,
                    edge["from_id"],
                    edge["to_id"],
                    edge.get("relation", "RELATED_TO"),
                    edge.get("attributes", {}),
                )

    async def query_context(self, query: str, limit: int = 10) -> list[dict]:
        """
        Find nodes whose name or attributes match the query terms.
        Returns list of {node, relations} dicts.
        """
        terms = [t.lower() for t in query.split() if len(t) > 2]
        if not terms:
            return []

        # Build a simple CONTAINS filter across name and key attributes
        conditions = " OR ".join(
            f"toLower(n.name) CONTAINS '{t}' OR toLower(n.notes) CONTAINS '{t}'"
            for t in terms[:5]
        )
        cypher = f"""
            MATCH (n)
            WHERE {conditions}
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n, collect({{relation: type(r), target: m.name, target_type: labels(m)}}) AS rels
            LIMIT {limit}
        """
        async with self._driver.session() as session:
            result = await session.run(cypher)
            rows = await result.data()
        return rows

    async def get_graph_summary(self, limit: int = 150) -> str:
        """Return a human-readable summary of the entire knowledge graph."""
        cypher = """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN n, collect({rel: type(r), to_name: m.name, to_type: m.type}) AS rels
            LIMIT $limit
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, limit=limit)
            rows = await result.data()

        if not rows:
            return ""

        lines: list[str] = []
        for row in rows:
            n = dict(row["n"])
            name = n.get("name", "?")
            ntype = n.get("type", "Entity")
            attrs = {k: v for k, v in n.items() if k not in ("name", "type", "id")}
            line = f"[{ntype}] {name}"
            if attrs:
                line += " — " + ", ".join(f"{k}: {v}" for k, v in attrs.items())
            for rel in row.get("rels", []):
                if rel.get("to_name"):
                    line += f"\n  → {rel['rel']} [{rel.get('to_type', '')}] {rel['to_name']}"
            lines.append(line)
        return "\n".join(lines)

    async def delete_nodes(self, ids: list[str]) -> None:
        """Remove nodes and all their relationships by id."""
        if not ids:
            return
        async with self._driver.session() as session:
            await session.run(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                ids=ids,
            )

    async def merge_duplicate_nodes(
        self, keep_id: str, remove_ids: list[str], merged_attributes: dict
    ) -> None:
        """
        Merge duplicate nodes into one:
        copy merged_attributes onto the kept node, then delete duplicates.
        Note: relationships of removed nodes are lost (no APOC required).
        """
        if not remove_ids:
            return
        async with self._driver.session() as session:
            for dup_id in remove_ids:
                await session.run(
                    """
                    MATCH (keep {id: $keep_id}), (dup {id: $dup_id})
                    SET keep += $attrs
                    DETACH DELETE dup
                    """,
                    keep_id=keep_id,
                    dup_id=dup_id,
                    attrs=merged_attributes,
                )

    async def format_context(self, query: str) -> str:
        """Return a human-readable context string for prompt injection."""
        rows = await self.query_context(query)
        if not rows:
            return ""
        parts: list[str] = []
        for row in rows:
            n = dict(row["n"])
            name = n.get("name", "?")
            node_type = n.get("type", "Entity")
            attrs = {k: v for k, v in n.items() if k not in ("name", "type", "id")}
            line = f"- {node_type} '{name}'"
            if attrs:
                line += ": " + ", ".join(f"{k}={v}" for k, v in attrs.items())
            rels = [r for r in row.get("rels", []) if r.get("target")]
            for rel in rels:
                line += f"\n  → {rel['relation']} {rel['target']}"
            parts.append(line)
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Transaction functions (must be top-level for neo4j driver)
# ---------------------------------------------------------------------------

async def _merge_node(
    tx: Any,
    node_id: str,
    node_type: str,
    name: str,
    attributes: dict,
) -> None:
    props = {"id": node_id, "name": name, "type": node_type, **attributes}
    set_clause = ", ".join(f"n.{k} = ${k}" for k in props)
    await tx.run(
        f"MERGE (n {{id: $id}}) SET n :{node_type}, {set_clause}",
        **props,
    )


async def _merge_edge(
    tx: Any,
    from_id: str,
    to_id: str,
    relation: str,
    attributes: dict,
) -> None:
    props = {**attributes}
    set_clause = (
        "SET " + ", ".join(f"r.{k} = ${k}" for k in props)
        if props
        else ""
    )
    await tx.run(
        f"""
        MATCH (a {{id: $from_id}}), (b {{id: $to_id}})
        MERGE (a)-[r:{relation}]->(b)
        {set_clause}
        """,
        from_id=from_id,
        to_id=to_id,
        **props,
    )
