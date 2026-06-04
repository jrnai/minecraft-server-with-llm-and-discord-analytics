# API Contract

## Paper Plugin to Backend

### `POST /api/minecraft/events`

Headers:

```text
X-Bridge-Token: <BRIDGE_TOKEN>
```

Body:

```json
{
  "type": "player_chat",
  "timestamp": "2026-06-04T12:00:00Z",
  "server": "main",
  "player": {
    "uuid": "uuid",
    "name": "Steve"
  },
  "data": {
    "message": "@Guide hello"
  }
}
```

### `GET /api/minecraft/commands?server=main`

Headers:

```text
X-Bridge-Token: <BRIDGE_TOKEN>
```

Response:

```json
[
  {
    "id": 1,
    "action": "minecraft_whisper",
    "target": "Steve",
    "message": "[Guide] I am online."
  }
]
```

Allowed actions:

- `minecraft_chat`
- `minecraft_whisper`
- `minecraft_broadcast`

### `GET /api/minecraft/commands.txt?server=main`

This is the endpoint used by the Java Paper plugin. It avoids adding a JSON parser dependency to the plugin jar.

Headers:

```text
X-Bridge-Token: <BRIDGE_TOKEN>
```

Response format:

```text
id<TAB>action<TAB>base64_target<TAB>base64_message
```

Example:

```text
2	minecraft_chat	QWxleA==	W0d1aWRlXSBIZWxsbyE=
```

## Dashboard and Bot APIs

- `GET /api/status`
- `GET /api/players`
- `GET /api/events?limit=100`
- `GET /api/ai/logs?limit=100`
- `GET /api/metrics/uptime`
- `GET /api/llm/status`
- `POST /api/ai/ask`
- `POST /api/admin/broadcast`
- `POST /api/admin/whisper`
- `POST /api/analyst/reports`
- `GET /api/analyst/reports/latest`
- `GET /api/analyst/reports`
- `WS /ws/dashboard`

## Discord Bot Commands

- `/dashboard`: show the configured dashboard URL.
- `/status`: read `/api/status`.
- `/players`: read `/api/players`.
- `/ask`: call `/api/ai/ask`.
- `/analyst`: generate a public AI server report for the last hour, day, or week.
- `/recap`: generate a daily AI server recap.
- `/say`: call `/api/admin/broadcast` to speak in Minecraft.
- `/tell`: call `/api/admin/whisper` to message one Minecraft player.
- `/summary`: summarize recent `/api/events`.
- `/uptime`: read `/api/metrics/uptime`.
