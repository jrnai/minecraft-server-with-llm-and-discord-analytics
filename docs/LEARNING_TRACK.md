# Learning Track

## Stage 1: Networking Basics

- Learn HTTP request/response with the Paper plugin posting events.
- Inspect JSON payloads in FastAPI docs.
- Learn auth headers with `X-Bridge-Token` and `X-Admin-Token`.
- Learn polling by following `/api/minecraft/commands`.

## Stage 2: Backend and Databases

- Read `backend/app/main.py` for API flow.
- Read `backend/app/models.py` for database schema.
- Add one new event type, then show it on the dashboard.
- Add one new metric query.

## Stage 3: LLM Fundamentals

- Start with `LLM_PROVIDER=mock`.
- Switch to Groq or Ollama using `openai_compatible`.
- Change `backend/app/memory.py` and observe response quality.
- Add 20 evaluation questions in a notes file and test prompt changes manually.

## Stage 4: Discord Integration

- Register a Discord application and bot.
- Add bot to a private test server.
- Test `/status`, `/players`, `/ask`, `/summary`, and `/uptime`.
- Add role checks before creating moderation commands.

## Stage 5: Dashboard Engineering

- Add filters to Chat & Events.
- Add TPS once the Paper plugin emits it.
- Add AI latency charts from `/api/ai/logs`.
- Add player detail pages.

## Stage 6: Local AI and MLOps

- Install Ollama.
- Test small models first.
- Track response latency and failed requests.
- Compare local model quality against cloud model quality.
- Keep a cloud fallback for complex reasoning.

## Stage 7: Autonomous Agent Later

- Add Mineflayer as a separate service.
- Use backend-created goals.
- Require approval for destructive tasks.
- Log every action and result.
- Test only in a separate world first.

