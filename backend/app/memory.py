from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import PlayerSession, ServerEvent


def recent_context(db: Session, limit: int = 12) -> str:
    events = (
        db.query(ServerEvent)
        .order_by(desc(ServerEvent.timestamp), desc(ServerEvent.id))
        .limit(limit)
        .all()
    )
    lines: list[str] = []
    for event in reversed(events):
        player = event.player_name or "server"
        if event.type == "player_chat":
            lines.append(f"{player}: {event.data.get('message', '')}")
        elif event.type == "player_snapshot":
            continue
        else:
            lines.append(f"{event.type}: {player} {event.data}")
    player_state = online_player_context(db)
    if player_state:
        lines.append("")
        lines.append("Current online player state:")
        lines.extend(player_state)
    return "\n".join(lines)


def online_player_context(db: Session) -> list[str]:
    sessions = db.query(PlayerSession).filter(PlayerSession.left_at.is_(None)).all()
    lines: list[str] = []
    for session in sessions:
        snapshot = (
            db.query(ServerEvent)
            .filter(
                ServerEvent.type == "player_snapshot",
                ServerEvent.player_uuid == session.player_uuid,
            )
            .order_by(desc(ServerEvent.timestamp), desc(ServerEvent.id))
            .first()
        )
        latest_activity = (
            db.query(ServerEvent)
            .filter(
                ServerEvent.player_uuid == session.player_uuid,
                ServerEvent.type != "player_snapshot",
            )
            .order_by(desc(ServerEvent.timestamp), desc(ServerEvent.id))
            .first()
        )
        if not snapshot:
            lines.append(f"- {session.player_name}: online, no location snapshot yet.")
            continue

        data = snapshot.data or {}
        activity_text = format_activity(latest_activity)
        nearby = data.get("nearbyPlayers") or []
        nearby_text = ", ".join(nearby) if nearby else "no nearby players recorded"
        lines.append(
            f"- {session.player_name}: online in {data.get('world', 'unknown')} at "
            f"X={data.get('x', '?')} Y={data.get('y', '?')} Z={data.get('z', '?')}; "
            f"health={data.get('health', '?')}, food={data.get('food', '?')}, "
            f"gamemode={data.get('gameMode', '?')}, holding={data.get('heldItem', '?')}; "
            f"nearby={nearby_text}; latest activity={activity_text}."
        )
    return lines


def format_activity(event: ServerEvent | None) -> str:
    if not event:
        return "joined or idle"
    if event.type == "player_chat":
        return f"said {event.data.get('message', '')!r}"
    if event.type == "block_break":
        return f"broke {event.data.get('material', 'a block')}"
    if event.type == "block_place":
        return f"placed {event.data.get('material', 'a block')}"
    if event.type == "player_death":
        return f"died: {event.data.get('message', '')}"
    if event.type == "player_advancement":
        return f"earned advancement {event.data.get('key', '')}"
    return event.type


def assistant_prompt(ai_name: str, question: str, context: str, player_name: str | None = None) -> str:
    player_line = f"The current player is {player_name}." if player_name else "The request came from outside Minecraft."
    return f"""You are {ai_name}, a chaotic Minecraft server assistant NPC.
Your highest priority is being useful: answer the player's actual question using the server context before making jokes.
Your style is offensive-comedy flavored, sarcastic, rude in a playful way, profanity-friendly, and funny enough that players understand it is a bit.
You may swear, roast bad ideas, tease players, and use dramatic overconfidence, but the answer must still contain the useful facts.
If asked where a player is, use the Current online player state coordinates when available.
If asked what a player is doing, use latest activity, held item, nearby players, world, and coordinates. If the data is weak, say exactly what you know and what you cannot know yet.
Do not use slurs, hate, sexual content, real threats, self-harm content, or targeted harassment.
Do not bully protected traits or keep attacking a player after they ask you to stop.
Keep responses short: usually 1-3 sentences.
You cannot execute arbitrary commands. You may only choose one of:
- minecraft_chat
- minecraft_whisper
- minecraft_broadcast

Return only JSON with keys: response, action, target.

{player_line}

Recent server context:
{context or "No recent context yet."}

Request:
{question}
"""
