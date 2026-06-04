from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ServerEvent(Base):
    __tablename__ = "server_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    server: Mapped[str] = mapped_column(String(80), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    player_uuid: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    player_name: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class PlayerSession(Base):
    __tablename__ = "player_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_uuid: Mapped[str] = mapped_column(String(64), index=True)
    player_name: Mapped[str] = mapped_column(String(64), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlayerIdentity(Base):
    __tablename__ = "player_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    player_name: Mapped[str] = mapped_column(String(64), index=True)
    discord_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QueuedCommand(Base):
    __tablename__ = "queued_commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiLog(Base):
    __tablename__ = "ai_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_event_id: Mapped[int | None] = mapped_column(ForeignKey("server_events.id"), nullable=True)
    source_event: Mapped[ServerEvent | None] = relationship()


class AnalystReport(Base):
    __tablename__ = "analyst_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text)
    highlights: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(80), default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
