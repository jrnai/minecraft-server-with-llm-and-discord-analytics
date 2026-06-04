# Server Runbook

Use this when you want to shut everything down cleanly or start the server again later.

## Turn Everything Off

### 1. Stop Minecraft Paper

In the Paper server console, type:

```text
stop
```

Wait until the console finishes saving chunks and closes.

### 2. Stop Docker Services

From PowerShell:

```powershell
cd C:\mcserver
docker compose --profile discord down
```

This stops:

- backend API
- dashboard
- PostgreSQL
- Discord bot

Your database data stays because PostgreSQL uses a Docker named volume.

### 3. Stop playit.gg

Close the playit app/window, or press `Ctrl+C` in the playit terminal if you started it from a console.

## Turn Everything Back On

### 1. Start Docker Services

From PowerShell:

```powershell
cd C:\mcserver
docker compose --profile discord up -d
```

### 2. Start playit.gg

Open the playit app or run the playit agent the same way you did during setup.

Friends join through:

```text
corporation-encounter.gl.joinmc.link
```

### 3. Start Minecraft Paper

From PowerShell:

```powershell
cd C:\mcserver\paper-server
& "C:\Program Files\Java\jdk-26.0.1\bin\java.exe" -Xms2G -Xmx4G -jar paper-26.1.2-69.jar nogui
```

Keep this PowerShell window open. It is the Minecraft server console.

## Local URLs

Dashboard:

```text
http://localhost:5173
```

Backend health:

```text
http://localhost:8000/api/health
```

Backend API docs:

```text
http://localhost:8000/docs
```

## Check Status

Docker services:

```powershell
cd C:\mcserver
docker compose ps
```

Recent backend logs:

```powershell
cd C:\mcserver
docker compose logs backend --tail 80
```

Recent Discord bot logs:

```powershell
cd C:\mcserver
docker compose logs discord-bot --tail 80
```

## Recommended Order

Turn off:

```text
Minecraft Paper -> Docker -> playit.gg
```

Turn on:

```text
Docker -> playit.gg -> Minecraft Paper
```

