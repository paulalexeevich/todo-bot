"""
End-to-end mock test for task_agent.py
Simulates LangChain LLM responses to verify agent logic without a real API key.
"""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, "/tmp/idea-bot")

from agent.task_agent import process_task


def _tool_call_response(name: str, args: dict):
    """Build a fake LangChain AIMessage with a tool_call."""
    from langchain_core.messages import AIMessage
    return AIMessage(
        content="",
        tool_calls=[{"id": "call_test_01", "name": name, "args": args}],
    )


def _text_response(text: str):
    """Build a fake LangChain AIMessage with plain text (no tool call)."""
    from langchain_core.messages import AIMessage
    return AIMessage(content=text, tool_calls=[])


class TestTaskAgent(unittest.IsolatedAsyncioTestCase):

    async def _run(self, task_text: str, llm_responses: list, clarification_answer=None):
        """
        Run process_task with mocked LangChain LLM.
        llm_responses: list of AIMessages returned on successive ainvoke() calls.
        """
        call_count = 0
        saved_api_calls = []

        async def fake_ainvoke(messages, **kwargs):
            nonlocal call_count
            resp = llm_responses[min(call_count, len(llm_responses) - 1)]
            call_count += 1
            return resp

        async def fake_data_api(method, path, body, api_url, api_key):
            saved_api_calls.append({"method": method, "path": path, "body": body})
            if method == "POST" and path == "/tasks":
                return {"id": 42}
            return {"ok": True}

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = fake_ainvoke

        with patch("agent.task_agent._get_llm", return_value=mock_llm), \
             patch("agent.task_agent._call_data_api", side_effect=fake_data_api):

            result = await process_task(
                task_text,
                api_url="http://mock",
                api_key="mock-key",
                llm_provider="gemini",
                google_gemini_api_key="mock-gemini-key",
                clarification_answer=clarification_answer,
            )
        return result, saved_api_calls

    # ──────────────────────────────────────────────────────────────────────────
    # Test 1: reminder with full date + time extracted
    # ──────────────────────────────────────────────────────────────────────────
    async def test_reminder_full_datetime(self):
        """'Remind me to call Olga at 22:27 pm' → reminder with due_date=today, due_time=22:27"""
        response = _tool_call_response("save_reminder", {
            "text": "Remind me to call Olga at 22:27 pm",
            "title": "Call Olga",
            "due_date": "2026-03-29",
            "due_time": "22:27",
        })
        result, calls = await self._run("Remind me to call Olga at 22:27 pm", [response])

        self.assertEqual(result["type"], "reminder")
        self.assertEqual(result["due_date"], "2026-03-29")
        self.assertEqual(result["due_time"], "22:27")
        self.assertEqual(result["task_id"], 42)
        print(f"\n✓ Reminder: {result}")

    # ──────────────────────────────────────────────────────────────────────────
    # Test 2: complex multi-part task
    # ──────────────────────────────────────────────────────────────────────────
    async def test_complex_meeting_task(self):
        """Multi-part: meeting next Tuesday 2pm + remind 30min before → agent picks save_reminder"""
        response = _tool_call_response("save_reminder", {
            "text": "schedule a meeting with product team next Tuesday at 2pm, remind me 30 min before",
            "title": "Product team Q2 roadmap meeting",
            "due_date": "2026-04-07",   # next Tuesday from 2026-03-29
            "due_time": "13:30",        # 30 min before 14:00
        })
        result, calls = await self._run(
            "schedule a meeting with product team next Tuesday at 2pm, remind me 30 min before",
            [response],
        )
        self.assertEqual(result["type"], "reminder")
        self.assertIsNotNone(result.get("due_date"))
        self.assertIsNotNone(result.get("due_time"))
        print(f"\n✓ Complex meeting task: {result}")

    # ──────────────────────────────────────────────────────────────────────────
    # Test 3: clarification needed (reminder missing time)
    # ──────────────────────────────────────────────────────────────────────────
    async def test_reminder_needs_clarification_then_saves(self):
        """'Remind me to submit the report tomorrow' → ask for time → user says 10am → save"""
        ask_response = _tool_call_response("ask_clarification", {
            "question": "At what time should I remind you tomorrow?",
        })
        save_response = _tool_call_response("save_reminder", {
            "text": "Remind me to submit the report tomorrow",
            "title": "Submit the report",
            "due_date": "2026-03-30",
            "due_time": "10:00",
        })

        # First call: clarification needed
        result1, _ = await self._run("Remind me to submit the report tomorrow", [ask_response])
        self.assertIn("clarification_needed", result1)
        print(f"\n✓ Asked clarification: {result1['clarification_needed']}")

        # Second call: answer provided
        result2, _ = await self._run(
            "Remind me to submit the report tomorrow",
            [save_response],
            clarification_answer="at 10am",
        )
        self.assertEqual(result2["type"], "reminder")
        self.assertEqual(result2["due_time"], "10:00")
        print(f"✓ After clarification: {result2}")

    # ──────────────────────────────────────────────────────────────────────────
    # Test 4: shopping task
    # ──────────────────────────────────────────────────────────────────────────
    async def test_shopping_task(self):
        """'Buy a standing desk, need it by end of next week' → shopping"""
        response = _tool_call_response("save_task", {
            "text": "buy a standing desk, need it delivered by end of next week",
            "title": "Standing desk",
            "type": "shopping",
            "due_date": "2026-04-05",
        })
        result, _ = await self._run(
            "buy a standing desk, need it delivered by end of next week",
            [response],
        )
        self.assertEqual(result["type"], "shopping")
        print(f"\n✓ Shopping: {result}")

    # ──────────────────────────────────────────────────────────────────────────
    # Test 5: todo vs reminder disambiguation
    # ──────────────────────────────────────────────────────────────────────────
    async def test_todo_not_reminder(self):
        """'Refactor auth module before release' → todo, NOT reminder"""
        response = _tool_call_response("save_task", {
            "text": "refactor auth module before the release",
            "title": "Refactor auth module",
            "type": "todo",
        })
        result, _ = await self._run("refactor auth module before the release", [response])
        self.assertEqual(result["type"], "todo")
        print(f"\n✓ Todo (not reminder): {result}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
