# Idea Bot — CLAUDE.md

## Project Overview

A personal Telegram bot that collects startup ideas and runs overnight AI-powered discovery validation. Each idea gets researched across Reddit, Hacker News, Product Hunt, and IndieHackers, then synthesized into a structured report with a score, verdict, competitor scan, and market size estimate.

---

## Architecture

```
Telegram free-text → python-telegram-bot v20+ (async)
                           │
                           ▼
                       SQLite DB
                           │
                   nightly JobQueue job
                           │
                           ▼
               LangGraph Discovery Pipeline
                  ├── reddit_node (PRAW)
                  ├── hackernews_node (Algolia HN Search API)
                  ├── producthunt_node (GraphQL API v2)
                  └── indiehackers_node (httpx + BeautifulSoup)
                           │ all parallel
                           ▼
                    synthesize_node (LLM)
                           │
                    SQLite + Telegram notify
```

## Key Design Decisions

- **LLM is abstracted**: `config.LLM_PROVIDER` (env var) selects Claude or OpenAI. Add new providers in `agent/nodes/synthesize.py` without touching other files.
- **Research nodes are independent**: Each node in `agent/nodes/` takes `idea_text: str` and returns `list[Source]`. They are independently testable with mocked HTTP.
- **SQLite only**: `aiosqlite` for async access. `PRAGMA foreign_keys = ON` is set on every connection. Schema lives in `db/database.py:init_db()`.
- **Single-user bot**: All messages are validated against `config.TELEGRAM_USER_ID`. Reject anything from unknown chat IDs immediately.
- **Nightly scheduling**: `bot/jobs/discovery.py` is registered via `application.job_queue.run_daily()` in `main.py`. Do not use system cron or a separate process.

---

## Project Structure

```
idea-bot/
├── CLAUDE.md               # this file
├── .env.example            # all required env vars documented
├── .env                    # gitignored — actual secrets
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── main.py                 # entry point
├── config.py               # pydantic-settings, loads .env once
├── db/
│   ├── database.py         # init_db(), get_db(), SQL helpers
│   └── models.py           # Idea, Discovery, Source dataclasses
├── bot/
│   ├── handlers/
│   │   ├── idea.py         # MessageHandler(filters.TEXT & ~filters.COMMAND)
│   │   └── commands.py     # /list, /report, /status, /debug_run
│   └── jobs/
│       └── discovery.py    # nightly batch: fetch pending → run pipeline → notify
├── agent/
│   ├── state.py            # DiscoveryState TypedDict
│   ├── graph.py            # builds + compiles StateGraph
│   └── nodes/
│       ├── reddit.py
│       ├── hackernews.py
│       ├── producthunt.py
│       ├── indiehackers.py
│       └── synthesize.py
├── tests/
│   ├── test_db.py
│   ├── test_nodes.py
│   └── test_pipeline.py
└── data/                   # gitignored — SQLite file lives here
```

---

## Environment Variables

All vars are defined in `config.py` via `pydantic-settings`. See `.env.example` for the full list. Required at startup:

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_USER_ID` | Your Telegram numeric user ID |
| `LLM_PROVIDER` | `claude` or `openai` |
| `ANTHROPIC_API_KEY` | Required if `LLM_PROVIDER=claude` |
| `OPENAI_API_KEY` | Required if `LLM_PROVIDER=openai` |
| `REDDIT_CLIENT_ID` | PRAW OAuth |
| `REDDIT_CLIENT_SECRET` | PRAW OAuth |
| `PRODUCT_HUNT_TOKEN` | PH GraphQL API |
| `DISCOVERY_HOUR` | UTC hour for nightly run (default: 2) |
| `DB_PATH` | Path to SQLite file (default: `./data/ideas.db`) |

---

## Database Schema

```sql
-- db/database.py:init_db()
CREATE TABLE IF NOT EXISTS ideas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status     TEXT DEFAULT 'pending'  -- pending | processing | done | error
);

CREATE TABLE IF NOT EXISTS discoveries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id        INTEGER NOT NULL REFERENCES ideas(id),
    ran_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reddit_summary TEXT,
    hn_summary     TEXT,
    ph_summary     TEXT,
    ih_summary     TEXT,
    verdict        TEXT,
    score          REAL,          -- 0.0–10.0
    market_size    TEXT,
    full_report    TEXT           -- JSON blob of raw Source objects
);
```

---

## LangGraph State

```python
# agent/state.py
class DiscoveryState(TypedDict):
    idea_text: str
    reddit_sources: list[Source]
    hn_sources: list[Source]
    ph_sources: list[Source]
    ih_sources: list[Source]
    discovery: DiscoveryResult | None  # filled by synthesize node
```

All 4 research nodes run in parallel via `StateGraph` fan-out. `synthesize_node` runs after all 4 complete.

---

## Source and DiscoveryResult Models

```python
# db/models.py
@dataclass
class Source:
    platform: str   # reddit | hackernews | producthunt | indiehackers
    title: str
    url: str
    snippet: str

@dataclass
class DiscoveryResult:
    verdict: str         # LLM narrative (2–4 sentences)
    score: float         # 0.0–10.0
    market_size: str     # rough TAM/SAM estimate
    competitors: list[str]
    sentiment_summary: str
```

---

## Telegram Behavior

| Input | Response |
|-------|----------|
| Any non-command message | "Idea #N saved. Discovery runs tonight at 02:00 UTC." |
| `/list` | Last 10 ideas with ID, truncated text, status emoji |
| `/report <id>` | Full formatted discovery report |
| `/status` | Pending/done counts + next scheduled run time |
| `/debug_run` | Manually triggers the nightly job immediately (for testing) |

---

## Running Locally

```bash
cp .env.example .env
# fill in .env

python -m venv .venv && source .venv/bin/activate
pip install -e .

python main.py
```

## Running with Docker

```bash
docker compose up -d
docker compose logs -f
```

---

## Testing

```bash
pytest tests/                          # all tests
pytest tests/test_nodes.py -v          # node unit tests (mocked HTTP)
pytest tests/test_pipeline.py -v       # full pipeline (mocked LLM + nodes)
```

- Node tests mock all HTTP with `respx` (httpx mock library) or `unittest.mock`
- Pipeline tests use a real in-memory SQLite DB and mocked LLM responses
- No external API calls in tests

---

## Code Conventions

- All async — never use `requests` or `time.sleep`; use `httpx.AsyncClient` and `asyncio`
- No global state outside `config.py`
- `config.py` is imported as `from config import settings` — instantiated once
- DB connection is always obtained via `async with get_db() as db:` context manager
- Each research node must be independently runnable: `asyncio.run(reddit_node(state, config))`
- LangGraph graph is compiled once at startup in `agent/graph.py` and reused
- Secrets never logged — mask tokens in any debug output

---

## Adding a New Research Source

1. Create `agent/nodes/<source>.py` with a single async function `async def <source>_node(state: DiscoveryState) -> dict`
2. Return `{"<source>_sources": list[Source]}`
3. Add a parallel edge in `agent/graph.py`
4. Add `<source>_summary: str | None` to the `discoveries` table (migration in `db/database.py`)
5. Update the synthesize prompt in `agent/nodes/synthesize.py` to include the new sources
6. Add tests in `tests/test_nodes.py`

---

## Deployment Notes

- Mount `./data` as a Docker volume to persist SQLite across container restarts
- Bot uses long polling by default — suitable for VPS; switch to webhooks for production scale
- `TELEGRAM_USER_ID` guard prevents the bot from responding to anyone else if the token leaks
