from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PlayerRef(BaseModel):
    uuid: str | None = None
    name: str | None = None


class MinecraftEventIn(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    timestamp: datetime | None = None
    server: str = "main"
    player: PlayerRef | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class CommandOut(BaseModel):
    id: int
    action: Literal["minecraft_chat", "minecraft_whisper", "minecraft_broadcast"]
    target: str | None = None
    message: str


class AiAction(BaseModel):
    response: str = Field(min_length=1, max_length=1000)
    action: Literal["minecraft_chat", "minecraft_whisper", "minecraft_broadcast"] = "minecraft_chat"
    target: str | None = None


class BroadcastIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    server: str = "main"


class WhisperIn(BaseModel):
    target: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=500)
    server: str = "main"


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    source: str = "discord"
    player_name: str | None = None


class AnalystReportIn(BaseModel):
    period: Literal["hour", "day", "week"] = "day"
    source: str = Field(default="api", max_length=80)
