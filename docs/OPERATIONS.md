# Operations Checklist

## Daily Server Operations

- Start backend stack: `docker compose up -d`
- Start Paper server from its own folder.
- Check backend health: `http://localhost:8000/api/health`
- Check dashboard: `http://localhost:5173`
- Verify Paper logs do not show bridge token or backend connection errors.

## Safe Shutdown

1. Warn players in Minecraft or dashboard broadcast.
2. Stop Paper with `stop`.
3. Stop app stack:

```powershell
docker compose down
```

## Backup

Back up separately:

- Paper world folders: `world`, `world_nether`, `world_the_end`
- Paper config: `server.properties`, `plugins/`
- PostgreSQL data via dump

Database dump:

```powershell
docker compose exec postgres pg_dump -U mcserver mcserver > backups/mcserver.sql
```

## Restore

1. Stop Paper and Docker stack.
2. Restore world folders.
3. Start PostgreSQL only.
4. Restore database dump.
5. Start backend, dashboard, bot, then Paper.

## Profiling

Install spark on Paper and run:

```text
/spark profiler start
/spark profiler stop
```

Use the dashboard for application-level symptoms:

- event volume spikes
- AI latency
- player join/leave behavior
- chat/AI log review

## Security

- Keep `BRIDGE_TOKEN`, `ADMIN_TOKEN`, and `DISCORD_TOKEN` private.
- Do not publish backend port `8000` publicly.
- Put dashboard behind a tunnel or reverse proxy with authentication before exposing it.
- Keep LLM actions restricted to backend allowlists.
- Keep Paper plugin command execution limited to safe message actions.

