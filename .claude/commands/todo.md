Add a task to the todo-bot via the intelligent Claude agent.

**Task:** $ARGUMENTS

## Steps

1. Load environment from the `.env` file in the project root:
   - Read `DATA_API_URL` (default `http://localhost:8001`)
   - Read `DATA_API_KEY`
   - Read `LLM_PROVIDER` (default `gemini`)
   - Read the matching API key: `GOOGLE_GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`

2. Run the task agent:
   ```
   cd /tmp/idea-bot && python -m agent.task_agent <task text>
   ```
   Set all env vars from the `.env` file before running.

3. Parse the JSON output:
   - If `clarification_needed` is set → ask the user that question, then re-run with `--clarification "<answer>"`
   - If `task_id` is set → report success: task ID, type, title, and any reminder date/time
   - If `error` is set → report the error clearly

4. Format the result for the user in a clear, brief message.

## Example outputs
- `Task #42 saved as todo — "Refactor auth module"`
- `Reminder #43 set for 2026-04-01 at 15:00 UTC — "Call Olga"`
- `(clarification) When should I remind you? → user answers → saves`
