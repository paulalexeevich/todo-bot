"""
Intelligent task processor — LangChain tool-calling agent (provider-agnostic).
Connects to the memory agent via MCP to query and save long-term memory.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task tool schemas (locally-executed — LLM generates call, we run it)
# ---------------------------------------------------------------------------

class _SaveReminderInput(BaseModel):
    text: str = Field(description="Original task text verbatim")
    title: str = Field(description="Concise reminder title, max 60 chars")
    due_date: str = Field(description="ISO date YYYY-MM-DD")
    due_time: str = Field(description="24-hour time HH:MM (e.g. 15:00 for 3 pm)")


class _SaveTaskInput(BaseModel):
    text: str = Field(description="Original task text verbatim")
    title: str = Field(description="Concise task title, max 60 chars")
    type: str = Field(description="One of: todo, idea, note, learning, architecture, question, shopping")
    due_date: str = Field(default="", description="ISO date YYYY-MM-DD if mentioned, else empty")
    due_time: str = Field(default="", description="HH:MM if a time was mentioned, else empty")


class _AskClarificationInput(BaseModel):
    question: str = Field(description="The specific question to ask the user")


SYSTEM_PROMPT = """You are a personal task assistant with access to long-term memory.

When the user gives you a task or note:
1. First call query_memory to check what you already know about people or context mentioned.
2. Then call exactly one task tool: save_reminder, save_task, or ask_clarification.
3. If you learn something new and lasting (who someone is, a preference, a pattern),
   call save_memory before finishing.

Task tool guidelines:
- "remind", "alert me", "don't forget" + a time/date → save_reminder
- "buy", "find", "search for" a product → save_task type=shopping
- A startup/product concept → save_task type=idea
- Something to do without notification → save_task type=todo
- A fact, link, or reference → save_task type=note
- For reminders: if date OR time is missing, call ask_clarification first.
- "3 pm" → "15:00", "22:27 pm" → "22:27" (already 24h, ignore the pm suffix).
- Today is {today}."""

# ---------------------------------------------------------------------------
# Data API helper
# ---------------------------------------------------------------------------

async def _call_data_api(
    method: str, path: str, body: Optional[dict], api_url: str, api_key: str
) -> dict:
    async with httpx.AsyncClient(
        base_url=api_url, headers={"X-API-Key": api_key}, timeout=15.0
    ) as client:
        if method == "POST":
            r = await client.post(path, json=body)
        elif method == "PATCH":
            r = await client.patch(path, json=body)
        else:
            r = await client.get(path)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Local task tool execution
# ---------------------------------------------------------------------------

async def _execute_task_tool(
    name: str, args: dict, api_url: str, api_key: str
) -> tuple[str, Optional[dict]]:
    """Execute a local task tool. Returns (result_text, structured_result | None)."""
    if name == "save_reminder":
        task = await _call_data_api(
            "POST", "/tasks", {"text": args["text"], "type": "reminder"}, api_url, api_key
        )
        task_id = task["id"]
        await _call_data_api("PATCH", f"/tasks/{task_id}/reminder", {
            "due_date": args["due_date"],
            "due_time": args["due_time"],
        }, api_url, api_key)
        result = {
            "task_id": task_id,
            "type": "reminder",
            "title": args["title"],
            "due_date": args["due_date"],
            "due_time": args["due_time"],
        }
        return f"Reminder #{task_id} saved for {args['due_date']} at {args['due_time']} UTC.", result

    if name == "save_task":
        task = await _call_data_api(
            "POST", "/tasks", {"text": args["text"], "type": args["type"]}, api_url, api_key
        )
        task_id = task["id"]
        due_date = args.get("due_date") or None
        due_time = args.get("due_time") or None
        if due_date or due_time:
            await _call_data_api("PATCH", f"/tasks/{task_id}/reminder", {
                "due_date": due_date, "due_time": due_time,
            }, api_url, api_key)
        result = {"task_id": task_id, "type": args["type"], "title": args["title"]}
        return f"Task #{task_id} saved as {args['type']}.", result

    if name == "ask_clarification":
        return args["question"], {"clarification_needed": args["question"]}

    return f"Unknown tool: {name}", None


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _get_llm(provider: str, anthropic_key: str, openai_key: str, gemini_key: str):
    if provider == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-haiku-4-5-20251001", api_key=anthropic_key)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", api_key=openai_key)
    else:  # gemini (default)
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=gemini_key)


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

_TASK_TOOL_NAMES = {"save_reminder", "save_task", "ask_clarification"}


async def _run_agent(
    text: str,
    api_url: str,
    api_key: str,
    llm_provider: str,
    anthropic_api_key: str,
    openai_api_key: str,
    google_gemini_api_key: str,
    clarification_answer: Optional[str],
    mcp_tools: list,
) -> dict:
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
    from langchain_core.tools import StructuredTool

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _noop(**kwargs: Any) -> str:
        return ""

    task_tools = [
        StructuredTool.from_function(
            func=_noop, name="save_reminder", args_schema=_SaveReminderInput,
            description=(
                "Save a reminder. User will be notified at the given date and time. "
                "Use when the user wants to be reminded at a specific moment."
            ),
        ),
        StructuredTool.from_function(
            func=_noop, name="save_task", args_schema=_SaveTaskInput,
            description="Save a task that is NOT a reminder (todo, idea, note, learning, architecture, question, shopping).",
        ),
        StructuredTool.from_function(
            func=_noop, name="ask_clarification", args_schema=_AskClarificationInput,
            description="Ask the user for missing required information (date or time for a reminder).",
        ),
    ]

    # MCP tools (query_memory, save_memory, list_entities) are already LangChain StructuredTools
    mcp_tool_map = {t.name: t for t in mcp_tools}
    all_tools = task_tools + mcp_tools

    llm = _get_llm(llm_provider, anthropic_api_key, openai_api_key, google_gemini_api_key)
    llm_with_tools = llm.bind_tools(all_tools)

    messages: list = [
        SystemMessage(content=SYSTEM_PROMPT.format(today=today)),
        HumanMessage(content=text),
    ]
    if clarification_answer:
        messages.append(AIMessage(content="I need more information."))
        messages.append(HumanMessage(content=clarification_answer))

    for _ in range(8):  # extra iterations for memory queries
        response = await llm_with_tools.ainvoke(messages)

        if not response.tool_calls:
            content = response.content if isinstance(response.content, str) else "Saved."
            return {"task_id": None, "type": "note", "title": text[:60], "message": content}

        tool_call = response.tool_calls[0]
        name = tool_call["name"]
        args = tool_call["args"]
        call_id = tool_call["id"]

        messages.append(response)

        if name in mcp_tool_map:
            # MCP tool — delegate execution to the MCP server via LangChain adapter
            try:
                result_text = await mcp_tool_map[name].ainvoke(args)
            except Exception as e:
                result_text = f"Memory tool error: {e}"
            messages.append(ToolMessage(content=str(result_text), tool_call_id=call_id))
            # Continue the loop — LLM will now use the memory result to make next decision

        elif name in _TASK_TOOL_NAMES:
            result_text, structured = await _execute_task_tool(name, args, api_url, api_key)
            messages.append(ToolMessage(content=result_text, tool_call_id=call_id))
            if structured:
                return {**structured, "message": result_text}

        else:
            messages.append(ToolMessage(content=f"Unknown tool: {name}", tool_call_id=call_id))

    return {"task_id": None, "type": "note", "title": text[:60], "message": "Could not process task."}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def process_task(
    text: str,
    api_url: str,
    api_key: str,
    *,
    llm_provider: str = "gemini",
    anthropic_api_key: str = "",
    openai_api_key: str = "",
    google_gemini_api_key: str = "",
    memory_agent_url: str = "",
    clarification_answer: Optional[str] = None,
) -> dict:
    """
    Process a task using a tool-calling agent with optional long-term memory via MCP.

    If memory_agent_url is set, the agent gains query_memory / save_memory / list_entities
    tools that connect to the memory agent's MCP server. The LLM decides autonomously
    when to query or save memory.
    """
    mcp_tools: list = []

    if memory_agent_url:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            mcp_client = MultiServerMCPClient({
                "memory": {
                    "url": f"{memory_agent_url}/mcp",
                    "transport": "streamable_http",
                }
            })
            async with mcp_client as client:
                mcp_tools = client.get_tools()
                logger.info("Loaded %d MCP memory tools.", len(mcp_tools))
                return await _run_agent(
                    text, api_url, api_key,
                    llm_provider, anthropic_api_key, openai_api_key, google_gemini_api_key,
                    clarification_answer, mcp_tools,
                )
        except Exception as e:
            logger.warning("MCP connection failed (%s), running without memory.", e)

    # Fallback: no memory tools
    return await _run_agent(
        text, api_url, api_key,
        llm_provider, anthropic_api_key, openai_api_key, google_gemini_api_key,
        clarification_answer, [],
    )


# ---------------------------------------------------------------------------
# CLI entry point (used by the /todo Claude Code skill)
# ---------------------------------------------------------------------------

async def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Process a task with the agent")
    parser.add_argument("task", nargs="+", help="Task text")
    parser.add_argument("--clarification", default=None, help="Answer to a previous clarification question")
    args = parser.parse_args()

    text = " ".join(args.task)
    api_url = os.environ.get("DATA_API_URL", "http://localhost:8001")
    api_key = os.environ.get("DATA_API_KEY", "")
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    memory_url = os.environ.get("MEMORY_AGENT_URL", "")

    result = await process_task(
        text,
        api_url=api_url,
        api_key=api_key,
        llm_provider=provider,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        google_gemini_api_key=os.environ.get("GOOGLE_GEMINI_API_KEY", ""),
        memory_agent_url=memory_url,
        clarification_answer=args.clarification,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(_main())
