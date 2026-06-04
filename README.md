# Minecraft LLM Server Lab

This repository is a greenfield implementation of a Minecraft + LLM + Discord + dashboard learning stack.

It gives you:

- A Paper plugin source project that forwards Minecraft events to a backend and polls for safe commands.
- A FastAPI backend that stores events, tracks players, calls an LLM provider, and broadcasts dashboard updates.
- A Discord bot that queries the backend for server status, players, summaries, and AI answers.
- A React dashboard for server operations, chat/AI logs, metrics, and safe admin actions.
- Docker Compose for PostgreSQL, backend, dashboard, and bot.

## Repository Layout

```text
backend/          FastAPI API, database models, LLM provider layer
discord-bot/      discord.py slash-command bot
dashboard/        React + Vite + TypeScript dashboard
paper-plugin/     Java Paper plugin source
docs/             Operations, learning roadmap, and setup notes
```

## Quick Start

1. Copy `.env.example` to `.env` and fill in secrets.
2. Install Docker Desktop.
3. Start the app stack:

```powershell
docker compose up --build
```

4. Open the dashboard:

```text
http://localhost:5173
```

5. Build the Paper plugin after installing Gradle or using an IDE with Gradle support:

```powershell
cd paper-plugin
gradle build
```

6. Copy the generated plugin jar from `paper-plugin/build/libs/` into your Paper server `plugins/` folder.

## Local Services

| Service | URL |
| --- | --- |
| Backend API | `http://localhost:8000` |
| Backend docs | `http://localhost:8000/docs` |
| Dashboard | `http://localhost:5173` |
| PostgreSQL | `localhost:5432` |

## First Milestone

The first complete loop is:

1. Player says `@Guide hello` in Minecraft.
2. Paper plugin posts a `player_chat` event to the backend.
3. Backend stores the event, calls the configured LLM provider, validates the response, and queues a chat command.
4. Paper plugin polls commands and broadcasts the AI response in Minecraft.
5. Discord bot and React dashboard read the same backend state.

## Start and Stop

For the exact day-to-day commands to start or shut down Docker, the Paper server, playit.gg, and the Discord bot, see:

```text
docs/RUNBOOK.md
```

## LLM Providers

The backend defaults to a mock provider so the system works before you configure API keys.

Cloud or Ollama-compatible providers use the same OpenAI-style configuration:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=your_key
LLM_MODEL=llama-3.1-8b-instant
```

For Ollama:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.2:3b
```

## Security Defaults

- The Paper plugin must send `X-Bridge-Token`.
- Admin dashboard writes require `X-Admin-Token`.
- The LLM can only produce allowlisted actions.
- The Paper plugin only executes `minecraft_chat`, `minecraft_whisper`, and `minecraft_broadcast` command types.
- Do not expose the backend directly to the public internet.
