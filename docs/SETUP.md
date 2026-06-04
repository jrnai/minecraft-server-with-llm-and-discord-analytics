# Setup Guide

## 1. Runtime Prerequisites

Install:

- Docker Desktop
- Java 26 for the Paper 26.1.2 server and plugin build
- Gradle, or an IDE that can import Gradle projects
- A Paper server jar from PaperMC
- Optional: Ollama for local models

Docker is the recommended run path. A local Python virtual environment can also be used for backend development.

## 2. Environment

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Change at least:

```env
BRIDGE_TOKEN=your-long-random-token
ADMIN_TOKEN=another-long-random-token
```

If you want Discord bot commands:

```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_test_server_id
DASHBOARD_PUBLIC_URL=http://localhost:5173
DISCORD_ANALYST_CHANNEL_ID=channel_id_for_daily_recaps
ANALYST_DAILY_HOUR=21
ANALYST_TIMEZONE=Asia/Kuala_Lumpur
```

For normal Discord messages like `chat hello`, enable **Message Content Intent** for your bot in the Discord Developer Portal.

## 3. Start Backend and Dashboard

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8000/docs
http://localhost:5173
```

Start the Discord bot too:

```powershell
docker compose --profile discord up --build
```

Discord slash commands:

- `/dashboard` shows the dashboard link and current server snapshot.
- `/status` shows server and AI status.
- `/players` lists known online/offline players.
- `/ask` asks the AI from Discord.
- `chat hello` in a Discord channel asks the AI without using a slash command.
- `/analyst` generates an AI server report for the last hour, day, or week.
- `/recap` generates a daily AI server recap on demand.
- `/say` broadcasts a Discord message into Minecraft chat.
- `/tell` whispers a Discord message to one Minecraft player.
- `/summary` summarizes recent server activity.
- `/uptime` shows simple activity counters.

`/say` and `/tell` use the backend `ADMIN_TOKEN`, so the bot must run with the same `.env` file as the backend.
If `DISCORD_ANALYST_CHANNEL_ID` is set, the bot posts one automatic daily recap at `ANALYST_DAILY_HOUR`.

## 3a. Optional Local Backend Development

A local backend venv lives at:

```text
backend/.venv
```

Run local backend commands with:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

If plain `python` still resolves to `WindowsApps`, use the venv Python directly as shown above.

## 4. Build and Install Paper Plugin

```powershell
cd paper-plugin
$env:JAVA_HOME="C:\Program Files\Java\jdk-26.0.1"
$env:Path="$env:JAVA_HOME\bin;$env:Path"
gradle build
```

Copy:

```text
paper-plugin/build/libs/minecraft-llm-bridge-0.1.0.jar
```

to:

```text
your-paper-server/plugins/
```

Start the server once, then edit:

```text
plugins/MinecraftLlmBridge/config.yml
```

Set:

```yaml
backend-url: "http://localhost:8000"
bridge-token: "same value as BRIDGE_TOKEN"
server-name: "main"
```

Restart Paper.

## 5. First End-to-End Test

In Minecraft chat:

```text
chat hello
```

Expected result:

- Backend receives a `player_chat` event.
- Dashboard updates.
- Backend queues an AI response.
- Paper plugin broadcasts or whispers `[Guide] ...`.

With `LLM_PROVIDER=mock`, the response is deterministic and does not need an API key.

## 6. Use Groq Free API First

Create a Groq API key at:

```text
https://console.groq.com/keys
```

Set this in `.env`:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=your_groq_api_key
LLM_MODEL=llama-3.1-8b-instant
```

Restart:

```powershell
docker compose up -d --build backend
```

The backend uses Groq's OpenAI-compatible Chat Completions endpoint, so no separate Groq SDK is needed.

## 7. Switch to Ollama Later

Install Ollama, pull a small model, and run:

```powershell
ollama pull llama3.2:3b
```

Use this in `.env`:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.2:3b
```

Restart:

```powershell
docker compose up --build
```
