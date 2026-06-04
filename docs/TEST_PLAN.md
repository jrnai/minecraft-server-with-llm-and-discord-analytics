# Test Plan

## Backend

- `GET /api/health` returns `{ "ok": true }`.
- `POST /api/minecraft/events` rejects missing or bad `X-Bridge-Token`.
- Valid `player_join` creates or updates a player identity.
- Valid `player_leave` closes the active session.
- `player_chat` without `chat` logs only the event.
- `player_chat` with `chat` creates an AI log and queues one command.
- Malformed JSON returns a validation error without crashing.
- `POST /api/admin/broadcast` rejects missing or bad `X-Admin-Token`.

## Paper Plugin

- Join, leave, chat, death, and advancement events reach backend.
- Plugin keeps running if backend is offline.
- Polling receives queued commands and marks them delivered.
- Unsupported backend command actions are ignored.

## Discord Bot

- `/status` returns backend state.
- `/players` handles empty player list.
- `/ask` returns an AI response.
- Discord message `chat hello` returns an AI response.
- Discord messages without `chat` are ignored by the AI.
- `/summary` handles empty event history.
- Bot startup fails fast when `DISCORD_TOKEN` is missing.

## Dashboard

- Initial load renders status, players, events, AI logs, and metrics.
- WebSocket reconnect state is visible.
- Broadcast form sends admin token.
- Long chat and AI messages wrap without breaking layout.

## Failure Scenarios

- Ollama is offline.
- Cloud LLM key is invalid.
- PostgreSQL is unavailable.
- Paper server restarts while backend remains running.
- Backend restarts while Paper plugin keeps polling.
- Discord API is unavailable.
