from datetime import datetime, timezone
from base64 import b64encode

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.actions import sanitize_ai_action
from app.analyst import generate_analyst_report, serialize_report
from app.config import settings
from app.dashboard_ws import hub
from app.database import Base, engine, get_db
from app.llm import complete_ai_action
from app.memory import assistant_prompt, recent_context
from app.models import AiLog, AnalystReport, PlayerIdentity, PlayerSession, QueuedCommand, ServerEvent
from app.schemas import AnalystReportIn, AskIn, BroadcastIn, CommandOut, MinecraftEventIn, WhisperIn
from app.security import require_admin_token, require_bridge_token

app = FastAPI(title="Minecraft LLM Server Lab", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "server": settings.server_name, "ai": settings.ai_name}


@app.get("/api/status")
def status(db: Session = Depends(get_db)) -> dict:
    online_players = (
        db.query(PlayerSession)
        .filter(PlayerSession.left_at.is_(None))
        .count()
    )
    last_event = db.query(ServerEvent).order_by(desc(ServerEvent.timestamp), desc(ServerEvent.id)).first()
    return {
        "server": settings.server_name,
        "online": True,
        "onlinePlayers": online_players,
        "aiName": settings.ai_name,
        "llmProvider": settings.llm_provider,
        "llmModel": settings.llm_model,
        "lastEventAt": last_event.timestamp if last_event else None,
    }


@app.post("/api/minecraft/events", dependencies=[Depends(require_bridge_token)])
async def ingest_minecraft_event(event_in: MinecraftEventIn, db: Session = Depends(get_db)) -> dict:
    event = ServerEvent(
        type=event_in.type,
        server=event_in.server,
        timestamp=event_in.timestamp or datetime.now(timezone.utc),
        player_uuid=event_in.player.uuid if event_in.player else None,
        player_name=event_in.player.name if event_in.player else None,
        data=event_in.data,
    )
    db.add(event)
    update_player_state(db, event)
    db.commit()
    db.refresh(event)

    await hub.broadcast({"type": "event", "event": serialize_event(event)})

    queued = 0
    if event.type == "player_chat":
        message = str(event.data.get("message", ""))
        if settings.ai_trigger.lower() in message.lower():
            queued = await respond_to_player_message(db, event, message)

    return {"ok": True, "eventId": event.id, "queuedCommands": queued}


@app.get("/api/minecraft/commands", dependencies=[Depends(require_bridge_token)], response_model=list[CommandOut])
def poll_commands(server: str = "main", limit: int = 20, db: Session = Depends(get_db)) -> list[QueuedCommand]:
    return consume_commands(db, server, limit)


@app.get("/api/minecraft/commands.txt", dependencies=[Depends(require_bridge_token)], response_class=PlainTextResponse)
def poll_commands_text(server: str = "main", limit: int = 20, db: Session = Depends(get_db)) -> str:
    commands = consume_commands(db, server, limit)
    lines = []
    for command in commands:
        target = b64encode((command.target or "").encode("utf-8")).decode("ascii")
        message = b64encode(command.message.encode("utf-8")).decode("ascii")
        lines.append(f"{command.id}\t{command.action}\t{target}\t{message}")
    return "\n".join(lines)


@app.get("/api/events")
def events(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(ServerEvent).order_by(desc(ServerEvent.timestamp), desc(ServerEvent.id)).limit(min(limit, 500)).all()
    return [serialize_event(row) for row in rows]


@app.get("/api/players")
def players(db: Session = Depends(get_db)) -> list[dict]:
    identities = db.query(PlayerIdentity).order_by(PlayerIdentity.player_name).all()
    open_sessions = {
        session.player_uuid
        for session in db.query(PlayerSession).filter(PlayerSession.left_at.is_(None)).all()
    }
    return [
        {
            "uuid": identity.player_uuid,
            "name": identity.player_name,
            "discordId": identity.discord_id,
            "lastSeenAt": identity.last_seen_at,
            "online": identity.player_uuid in open_sessions,
        }
        for identity in identities
    ]


@app.get("/api/ai/logs")
def ai_logs(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(AiLog).order_by(desc(AiLog.created_at), desc(AiLog.id)).limit(min(limit, 500)).all()
    return [
        {
            "id": row.id,
            "provider": row.provider,
            "model": row.model,
            "response": row.response,
            "action": row.action,
            "target": row.target,
            "latencyMs": row.latency_ms,
            "createdAt": row.created_at,
        }
        for row in rows
    ]


@app.get("/api/metrics/uptime")
def uptime(db: Session = Depends(get_db)) -> dict:
    joins = db.query(func.count(ServerEvent.id)).filter(ServerEvent.type == "player_join").scalar()
    leaves = db.query(func.count(ServerEvent.id)).filter(ServerEvent.type == "player_leave").scalar()
    chats = db.query(func.count(ServerEvent.id)).filter(ServerEvent.type == "player_chat").scalar()
    return {"joins": joins or 0, "leaves": leaves or 0, "chatMessages": chats or 0}


@app.get("/api/llm/status")
def llm_status() -> dict:
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "baseUrl": settings.llm_base_url,
        "trigger": settings.ai_trigger,
    }


@app.get("/api/dashboard/snapshot")
def dashboard_snapshot(db: Session = Depends(get_db)) -> dict:
    online_sessions = db.query(PlayerSession).filter(PlayerSession.left_at.is_(None)).all()
    online_uuids = {session.player_uuid for session in online_sessions}
    identities = db.query(PlayerIdentity).order_by(PlayerIdentity.player_name).all()
    event_rows = db.query(ServerEvent).order_by(desc(ServerEvent.timestamp), desc(ServerEvent.id)).limit(8).all()
    ai_rows = db.query(AiLog).order_by(desc(AiLog.created_at), desc(AiLog.id)).limit(5).all()
    latest_report = db.query(AnalystReport).order_by(desc(AnalystReport.created_at), desc(AnalystReport.id)).first()
    last_event = db.query(ServerEvent).order_by(desc(ServerEvent.timestamp), desc(ServerEvent.id)).first()
    metrics = uptime(db)

    players = [
        {
            "uuid": identity.player_uuid,
            "name": identity.player_name,
            "online": identity.player_uuid in online_uuids,
            "lastSeenAt": identity.last_seen_at,
        }
        for identity in identities
    ]
    players.sort(key=lambda player: (not player["online"], player["name"].lower()))

    return {
        "generatedAt": datetime.now(timezone.utc),
        "status": {
            "server": settings.server_name,
            "online": True,
            "onlinePlayers": len(online_sessions),
            "aiName": settings.ai_name,
            "llmProvider": settings.llm_provider,
            "llmModel": settings.llm_model,
            "lastEventAt": last_event.timestamp if last_event else None,
        },
        "players": players[:8],
        "events": [serialize_event(row) for row in event_rows],
        "aiLogs": [
            {
                "id": row.id,
                "response": row.response,
                "action": row.action,
                "target": row.target,
                "latencyMs": row.latency_ms,
                "createdAt": row.created_at,
            }
            for row in ai_rows
        ],
        "metrics": metrics,
        "llm": llm_status(),
        "latestAnalystReport": serialize_report(latest_report) if latest_report else None,
    }


@app.post("/api/analyst/reports")
async def create_analyst_report(payload: AnalystReportIn, db: Session = Depends(get_db)) -> dict:
    report = await generate_analyst_report(db, payload.period, payload.source)
    await hub.broadcast({"type": "analystReport", "report": serialize_report(report)})
    return serialize_report(report)


@app.get("/api/analyst/reports/latest")
def latest_analyst_report(db: Session = Depends(get_db)) -> dict | None:
    report = db.query(AnalystReport).order_by(desc(AnalystReport.created_at), desc(AnalystReport.id)).first()
    return serialize_report(report) if report else None


@app.get("/api/analyst/reports")
def analyst_reports(limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(AnalystReport).order_by(desc(AnalystReport.created_at), desc(AnalystReport.id)).limit(min(limit, 100)).all()
    return [serialize_report(row) for row in rows]


@app.post("/api/admin/broadcast", dependencies=[Depends(require_admin_token)])
async def broadcast(payload: BroadcastIn, db: Session = Depends(get_db)) -> dict:
    command = QueuedCommand(server=payload.server, action="minecraft_broadcast", target=None, message=payload.message)
    db.add(command)
    db.commit()
    await hub.broadcast({"type": "commandQueued", "action": command.action, "message": command.message})
    return {"ok": True, "commandId": command.id}


@app.post("/api/admin/whisper", dependencies=[Depends(require_admin_token)])
async def whisper(payload: WhisperIn, db: Session = Depends(get_db)) -> dict:
    command = QueuedCommand(
        server=payload.server,
        action="minecraft_whisper",
        target=payload.target,
        message=payload.message,
    )
    db.add(command)
    db.commit()
    await hub.broadcast({"type": "commandQueued", "action": command.action, "target": command.target, "message": command.message})
    return {"ok": True, "commandId": command.id}


@app.post("/api/ai/ask")
async def ask_ai(payload: AskIn, db: Session = Depends(get_db)) -> dict:
    context = recent_context(db)
    prompt = assistant_prompt(settings.ai_name, payload.question, context, payload.player_name)
    result = await complete_ai_action(prompt, fallback_target=payload.player_name)
    action = sanitize_ai_action(result.action, fallback_target=payload.player_name)
    ai_log = AiLog(
        provider=settings.llm_provider,
        model=settings.llm_model,
        prompt=prompt,
        response=action.response,
        action=action.action,
        target=action.target,
        latency_ms=result.latency_ms,
    )
    db.add(ai_log)
    db.commit()
    await hub.broadcast({"type": "aiLog", "response": action.response, "source": payload.source})
    return {"response": action.response, "action": action.action, "target": action.target, "latencyMs": result.latency_ms}


@app.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket) -> None:
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(websocket)


def consume_commands(db: Session, server: str, limit: int) -> list[QueuedCommand]:
    commands = (
        db.query(QueuedCommand)
        .filter(QueuedCommand.server == server, QueuedCommand.delivered_at.is_(None))
        .order_by(QueuedCommand.created_at, QueuedCommand.id)
        .limit(min(limit, 50))
        .all()
    )
    now = datetime.now(timezone.utc)
    for command in commands:
        command.delivered_at = now
    db.commit()
    return commands


def update_player_state(db: Session, event: ServerEvent) -> None:
    if not event.player_uuid or not event.player_name:
        return
    identity = db.query(PlayerIdentity).filter(PlayerIdentity.player_uuid == event.player_uuid).first()
    if not identity:
        identity = PlayerIdentity(player_uuid=event.player_uuid, player_name=event.player_name)
        db.add(identity)
    identity.player_name = event.player_name
    identity.last_seen_at = event.timestamp

    if event.type == "player_join":
        db.add(PlayerSession(player_uuid=event.player_uuid, player_name=event.player_name, joined_at=event.timestamp))
    elif event.type == "player_leave":
        session = (
            db.query(PlayerSession)
            .filter(PlayerSession.player_uuid == event.player_uuid, PlayerSession.left_at.is_(None))
            .order_by(desc(PlayerSession.joined_at), desc(PlayerSession.id))
            .first()
        )
        if session:
            session.left_at = event.timestamp


async def respond_to_player_message(db: Session, event: ServerEvent, message: str) -> int:
    cleaned = message.replace(settings.ai_trigger, "").strip() or message
    prompt = assistant_prompt(settings.ai_name, cleaned, recent_context(db), event.player_name)
    result = await complete_ai_action(prompt, fallback_target=event.player_name)
    action = sanitize_ai_action(result.action, fallback_target=event.player_name)

    db.add(
        AiLog(
            provider=settings.llm_provider,
            model=settings.llm_model,
            prompt=prompt,
            response=action.response,
            action=action.action,
            target=action.target,
            latency_ms=result.latency_ms,
            source_event_id=event.id,
        )
    )
    db.add(QueuedCommand(server=event.server, action=action.action, target=action.target, message=f"[{settings.ai_name}] {action.response}"))
    db.commit()
    await hub.broadcast({"type": "aiResponse", "player": event.player_name, "response": action.response})
    return 1


def serialize_event(event: ServerEvent) -> dict:
    return {
        "id": event.id,
        "type": event.type,
        "server": event.server,
        "timestamp": event.timestamp,
        "player": {"uuid": event.player_uuid, "name": event.player_name},
        "data": event.data,
    }
