"""Fast single-call LLM task classifier. No LangGraph needed — one prompt, one response."""
import json
import logging
from dataclasses import dataclass, field

from config import settings

logger = logging.getLogger(__name__)

TASK_TYPES = {
    "idea": "startup idea, product concept, business opportunity to explore or validate",
    "todo": "action item, task, thing to build or do",
    "note": "reference info, fact, link, or resource to save",
    "learning": "lesson learned, personal insight, or discovery worth remembering",
    "architecture": "technical design decision, system architecture, or engineering choice",
    "question": "open question to research or think through",
    "shopping": "request to find and compare buying options for a product or item",
}

_TYPE_LIST = "\n".join(f'- {k}: {v}' for k, v in TASK_TYPES.items())


@dataclass
class TaskClassification:
    type: str
    title: str                      # short form, max ~60 chars
    reason: str                     # why this type was chosen
    search_query: str = ""          # cleaned search term (for shopping)
    location: str = "any"           # local | online | any (for shopping)


async def classify_task(text: str) -> TaskClassification:
    prompt = f"""Classify the following message into exactly one task type.

Message: "{text}"

Types:
{_TYPE_LIST}

Rules:
- If it mentions finding/buying/searching for a product to purchase → shopping
- If it describes a startup/product concept → idea
- If it starts with a verb and is actionable → todo
- If it records a decision or technical tradeoff → architecture
- If it's something the person learned → learning
- Default to note if nothing else fits

For shopping tasks also determine:
- location: "local" if the item typically requires visiting a physical store or is location-specific (food, haircut, local service, clothes fitting), "online" if it can be ordered and shipped anywhere, "any" if both work
- search_query: a clean search term optimized for finding the item (remove filler words, keep product + key attributes)

Respond with JSON only, no markdown:
{{"type": "...", "title": "...", "reason": "...", "search_query": "...", "location": "..."}}

Title should be a concise version of the message (max 60 chars).
search_query and location are only meaningful for shopping tasks; use "" and "any" otherwise."""

    try:
        result = await _call_llm(prompt)
        # strip possible markdown fences
        text_result = result.strip()
        if "```" in text_result:
            text_result = text_result.split("```")[1]
            if text_result.startswith("json"):
                text_result = text_result[4:]
        data = json.loads(text_result.strip())
        task_type = data.get("type", "note")
        if task_type not in TASK_TYPES:
            task_type = "note"
        location = data.get("location", "any")
        if location not in ("local", "online", "any"):
            location = "any"
        return TaskClassification(
            type=task_type,
            title=data.get("title", text[:60]),
            reason=data.get("reason", ""),
            search_query=data.get("search_query", text),
            location=location,
        )
    except Exception as e:
        logger.warning("Classification failed, defaulting to 'note': %s", e)
        return TaskClassification(type="note", title=text[:60], reason="classification failed")


async def _call_llm(prompt: str) -> str:
    if settings.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite-preview",
            google_api_key=settings.google_gemini_api_key,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        if isinstance(content, list):
            content = "".join(
                p.get("text", "") if isinstance(p, dict) else (p.text if hasattr(p, "text") else str(p))
                for p in content
            )
        return content

    elif settings.llm_provider == "claude":
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage
        llm = ChatAnthropic(model="claude-sonnet-4-6", api_key=settings.anthropic_api_key)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content

    elif settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        llm = ChatOpenAI(model="gpt-4o", api_key=settings.openai_api_key)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content

    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
