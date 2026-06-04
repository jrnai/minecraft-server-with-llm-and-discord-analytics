from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.llm import complete_text
from app.models import AiLog, AnalystReport, PlayerSession, ServerEvent


PERIOD_WINDOWS = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(days=7),
}


def period_start(period: str) -> datetime:
    return datetime.now(timezone.utc) - PERIOD_WINDOWS.get(period, PERIOD_WINDOWS["day"])


async def generate_analyst_report(db: Session, period: str, source: str) -> AnalystReport:
    since = period_start(period)
    events = (
        db.query(ServerEvent)
        .filter(ServerEvent.timestamp >= since)
        .order_by(ServerEvent.timestamp, ServerEvent.id)
        .limit(120)
        .all()
    )
    ai_logs = (
        db.query(AiLog)
        .filter(AiLog.created_at >= since)
        .order_by(desc(AiLog.created_at), desc(AiLog.id))
        .limit(20)
        .all()
    )
    open_sessions = db.query(PlayerSession).filter(PlayerSession.left_at.is_(None)).count()

    counts = dict(
        db.query(ServerEvent.type, func.count(ServerEvent.id))
        .filter(ServerEvent.timestamp >= since)
        .group_by(ServerEvent.type)
        .all()
    )
    event_lines = []
    for event in events[-40:]:
        player = event.player_name or "server"
        if event.type == "player_chat":
            detail = event.data.get("message", "")
        elif event.type == "player_death":
            detail = event.data.get("message", "")
        else:
            detail = str(event.data)[:180]
        event_lines.append(f"- {event.type}: {player} {detail}".strip())

    ai_lines = [f"- {log.action}: {log.response[:180]}" for log in ai_logs[:10]]
    prompt = f"""You are a public Minecraft server analyst.
Write a concise, funny, public-safe recap for the last {period}.
Use a playful roast style, but avoid private accusations, slurs, hate, threats, or sensitive moderation claims.
Include:
1. A one-line title.
2. A 2-4 sentence summary.
3. 3-5 bullet highlights.
4. One suggested next thing players should do.

Stats:
- Online players now: {open_sessions}
- Event counts: {counts}

Recent events:
{chr(10).join(event_lines) or "No events recorded."}

Recent AI moments:
{chr(10).join(ai_lines) or "No AI logs recorded."}
"""
    result = await complete_text(prompt)
    title, summary, highlights = parse_report_text(result.text, period)
    report = AnalystReport(period=period, title=title, summary=summary, highlights=highlights, source=source)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def parse_report_text(text: str, period: str) -> tuple[str, str, list[str]]:
    lines = [line.strip(" -*") for line in text.splitlines() if line.strip()]
    if not lines:
        return (f"{period.title()} server recap", "No report generated.", [])
    title = lines[0][:150]
    highlights = [line[:300] for line in lines[1:] if len(line) > 3][:6]
    summary = " ".join(highlights[:3]) if highlights else text[:700]
    if len(summary) > 900:
        summary = summary[:897] + "..."
    return title, summary, highlights


def serialize_report(report: AnalystReport) -> dict:
    return {
        "id": report.id,
        "period": report.period,
        "title": report.title,
        "summary": report.summary,
        "highlights": report.highlights,
        "source": report.source,
        "createdAt": report.created_at,
    }
