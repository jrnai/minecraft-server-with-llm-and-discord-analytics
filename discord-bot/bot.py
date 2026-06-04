import os
import asyncio
import textwrap
from io import BytesIO
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import discord
import httpx
from discord import app_commands
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DASHBOARD_URL = os.getenv("DASHBOARD_PUBLIC_URL", "http://localhost:5173")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
DISCORD_ANALYST_CHANNEL_ID = os.getenv("DISCORD_ANALYST_CHANNEL_ID")
ANALYST_DAILY_HOUR = int(os.getenv("ANALYST_DAILY_HOUR", "21"))
ANALYST_TIMEZONE = os.getenv("ANALYST_TIMEZONE", "Asia/Kuala_Lumpur")


class MinecraftLabBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=int(DISCORD_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        if DISCORD_ANALYST_CHANNEL_ID:
            self.loop.create_task(daily_analyst_loop())


client = MinecraftLabBot()


async def get_json(path: str) -> dict | list:
    async with httpx.AsyncClient(timeout=10) as http:
        response = await http.get(f"{BACKEND_URL}{path}")
        response.raise_for_status()
        return response.json()


async def post_json(path: str, payload: dict, *, admin: bool = False) -> dict:
    headers = {"X-Admin-Token": ADMIN_TOKEN} if admin else None
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(f"{BACKEND_URL}{path}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


@client.event
async def on_ready() -> None:
    print(f"Logged in as {client.user} at {datetime.now(timezone.utc).isoformat()}")


@client.tree.command(description="Show Minecraft server and AI status.")
async def status(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    data = await get_json("/api/status")
    embed = discord.Embed(title="Minecraft Server Status", color=discord.Color.green())
    embed.add_field(name="Server", value=str(data["server"]))
    embed.add_field(name="Online players", value=str(data["onlinePlayers"]))
    embed.add_field(name="AI", value=f'{data["aiName"]} ({data["llmProvider"]}/{data["llmModel"]})', inline=False)
    embed.add_field(name="Last event", value=str(data["lastEventAt"] or "none yet"), inline=False)
    await interaction.followup.send(embed=embed)


@client.tree.command(description="Show the Minecraft operations dashboard link.")
async def dashboard(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    try:
        data = await get_json("/api/dashboard/snapshot")
        image = render_dashboard_snapshot(data)
    except httpx.HTTPError as exc:
        await interaction.followup.send(f"Dashboard backend is offline or angry: `{exc}`")
        return
    except Exception as exc:
        await interaction.followup.send(f"Could not render dashboard snapshot: `{exc}`")
        return

    file = discord.File(image, filename="minecraft-dashboard.png")
    caption = dashboard_caption(data)
    await interaction.followup.send(content=caption, file=file)


@client.tree.command(description="List known players and who is currently online.")
async def players(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    data = await get_json("/api/players")
    if not data:
        await interaction.followup.send("No players have joined yet.")
        return
    lines = []
    for player in data[:20]:
        marker = "online" if player["online"] else "offline"
        lines.append(f'- {player["name"]}: {marker}')
    await interaction.followup.send("\n".join(lines))


@client.tree.command(description="Ask the Minecraft AI assistant a question.")
@app_commands.describe(question="Question to send to the AI assistant")
async def ask(interaction: discord.Interaction, question: str) -> None:
    await interaction.response.defer(thinking=True)
    data = await post_json("/api/ai/ask", {"question": question, "source": "discord"})
    await interaction.followup.send(data["response"])


@client.tree.command(description="Generate an AI analyst recap for the server.")
@app_commands.describe(period="Report window: hour, day, or week")
@app_commands.choices(
    period=[
        app_commands.Choice(name="hour", value="hour"),
        app_commands.Choice(name="day", value="day"),
        app_commands.Choice(name="week", value="week"),
    ]
)
async def analyst(interaction: discord.Interaction, period: app_commands.Choice[str]) -> None:
    await interaction.response.defer(thinking=True)
    try:
        report = await post_json("/api/analyst/reports", {"period": period.value, "source": "discord"})
    except httpx.HTTPError as exc:
        await interaction.followup.send(f"Analyst backend failed: `{exc}`")
        return
    await interaction.followup.send(embed=report_embed(report))


@client.tree.command(description="Generate a daily AI server recap.")
async def recap(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    try:
        report = await post_json("/api/analyst/reports", {"period": "day", "source": "discord-recap"})
    except httpx.HTTPError as exc:
        await interaction.followup.send(f"Recap failed: `{exc}`")
        return
    await interaction.followup.send(embed=report_embed(report))


@client.tree.command(description="Broadcast a Discord message into Minecraft chat.")
@app_commands.describe(message="Message to broadcast in Minecraft")
async def say(interaction: discord.Interaction, message: str) -> None:
    await interaction.response.defer(thinking=True)
    author = interaction.user.display_name
    text = f"[Discord] {author}: {message}"
    await post_json("/api/admin/broadcast", {"message": text}, admin=True)
    await interaction.followup.send("Sent to Minecraft.")


@client.tree.command(description="Whisper a Discord message to one Minecraft player.")
@app_commands.describe(player="Exact Minecraft player name", message="Message to send")
async def tell(interaction: discord.Interaction, player: str, message: str) -> None:
    await interaction.response.defer(thinking=True)
    author = interaction.user.display_name
    text = f"[Discord DM] {author}: {message}"
    await post_json("/api/admin/whisper", {"target": player, "message": text}, admin=True)
    await interaction.followup.send(f"Sent whisper to `{player}`.")


@client.tree.command(description="Summarize recent server activity.")
async def summary(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    events = await get_json("/api/events?limit=25")
    if not events:
        await interaction.followup.send("No server activity has been recorded yet.")
        return
    compact = []
    for event in events[:10]:
        player = event["player"]["name"] or "server"
        compact.append(f'{event["type"]}: {player}')
    question = "Summarize these recent Minecraft server events for Discord admins:\n" + "\n".join(compact)
    data = await post_json("/api/ai/ask", {"question": question, "source": "discord-summary"})
    await interaction.followup.send(data["response"])


@client.tree.command(description="Show simple uptime and activity counters.")
async def uptime(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    data = await get_json("/api/metrics/uptime")
    await interaction.followup.send(
        f'Joins: {data["joins"]} | Leaves: {data["leaves"]} | Chat messages: {data["chatMessages"]}'
    )


def render_dashboard_snapshot(data: dict) -> BytesIO:
    width, height = 1400, 1000
    image = Image.new("RGB", (width, height), "#f4f7f6")
    draw = ImageDraw.Draw(image)

    title_font = font(42, bold=True)
    heading_font = font(24, bold=True)
    label_font = font(18, bold=True)
    body_font = font(18)
    small_font = font(15)

    status_data = data.get("status", {})
    metrics = data.get("metrics", {})

    draw.text((42, 34), "Minecraft LLM Ops", fill="#4b6b62", font=label_font)
    draw.text((42, 62), f"{status_data.get('server', 'main')} dashboard", fill="#17202a", font=title_font)
    draw.text((1110, 56), "LIVE SNAPSHOT", fill="#16784d", font=label_font)
    draw.text((1110, 84), fmt_time(data.get("generatedAt")), fill="#66746f", font=small_font)

    metric_cards = [
        ("Online players", str(status_data.get("onlinePlayers", 0))),
        ("Assistant", str(status_data.get("aiName", "unknown"))),
        ("Chat messages", str(metrics.get("chatMessages", 0))),
        ("Provider", str(status_data.get("llmProvider", "unknown"))),
    ]
    x = 42
    for label, value in metric_cards:
        card(draw, x, 146, 315, 128)
        draw.text((x + 20, 166), label, fill="#66746f", font=small_font)
        draw_wrapped(draw, value, x + 20, 198, 270, 2, fill="#17202a", font=heading_font)
        x += 335

    panel(draw, 42, 306, 640, 284, "Players", heading_font)
    players = data.get("players", [])[:8]
    if not players:
        draw.text((70, 360), "No players recorded yet.", fill="#66746f", font=body_font)
    else:
        y = 354
        for player in players:
            online = bool(player.get("online"))
            draw.ellipse((70, y + 6, 84, y + 20), fill="#19a36c" if online else "#aab5b1")
            draw.text((98, y), str(player.get("name", "unknown")), fill="#17202a", font=label_font)
            draw.text((98, y + 24), "online" if online else "offline", fill="#66746f", font=small_font)
            y += 58

    panel(draw, 718, 306, 640, 284, "Activity Counters", heading_font)
    counter_rows = [
        ("Joins", metrics.get("joins", 0)),
        ("Leaves", metrics.get("leaves", 0)),
        ("Chat", metrics.get("chatMessages", 0)),
        ("Last event", fmt_time(status_data.get("lastEventAt"))),
        ("Model", status_data.get("llmModel", "unknown")),
    ]
    y = 360
    for label, value in counter_rows:
        draw.text((746, y), label, fill="#66746f", font=small_font)
        draw_wrapped(draw, str(value), 910, y - 2, 390, 1, fill="#17202a", font=body_font)
        y += 42

    panel(draw, 42, 626, 640, 312, "Recent Chat & Events", heading_font)
    events = data.get("events", [])[:8]
    if not events:
        draw.text((70, 680), "No events yet.", fill="#66746f", font=body_font)
    else:
        y = 676
        for event in events:
            player = event.get("player", {}).get("name") or "server"
            event_type = event.get("type", "event")
            event_data = event.get("data", {})
            message = str(event_data.get("message") or event_data.get("reason") or event_data)
            draw.text((70, y), f"{event_type} - {player}", fill="#227c68", font=small_font)
            y = draw_wrapped(draw, message, 70, y + 20, 570, 1, fill="#17202a", font=body_font) + 10
            if y > 910:
                break

    panel(draw, 718, 626, 640, 312, "AI Logs & Analyst", heading_font)
    report = data.get("latestAnalystReport")
    y = 676
    if report:
        draw.text((746, y), "Latest analyst recap", fill="#227c68", font=small_font)
        y = draw_wrapped(draw, str(report.get("summary", "")), 746, y + 22, 560, 3, fill="#17202a", font=body_font) + 18
    else:
        draw.text((746, y), "No analyst recap yet.", fill="#66746f", font=body_font)
        y += 44

    for log in data.get("aiLogs", [])[:5]:
        latency = round(float(log.get("latencyMs", 0)))
        draw.text((746, y), f"{log.get('action', 'ai')} - {latency} ms", fill="#227c68", font=small_font)
        y = draw_wrapped(draw, str(log.get("response", "")), 746, y + 20, 570, 1, fill="#17202a", font=body_font) + 12
        if y > 910:
            break

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output


def report_embed(report: dict) -> discord.Embed:
    embed = discord.Embed(
        title=str(report.get("title", "Server recap"))[:256],
        description=str(report.get("summary", ""))[:4000],
        color=discord.Color.gold(),
    )
    embed.add_field(name="Period", value=str(report.get("period", "day")), inline=True)
    embed.add_field(name="Generated", value=fmt_time(report.get("createdAt")), inline=True)
    highlights = report.get("highlights") or []
    if highlights:
        text = "\n".join(f"- {item}" for item in highlights[:5])
        embed.add_field(name="Highlights", value=text[:1000], inline=False)
    return embed


async def daily_analyst_loop() -> None:
    await client.wait_until_ready()
    last_posted_date: str | None = None
    tz = ZoneInfo(ANALYST_TIMEZONE)
    while not client.is_closed():
        now = datetime.now(tz)
        today = now.date().isoformat()
        if now.hour == ANALYST_DAILY_HOUR and last_posted_date != today:
            channel = client.get_channel(int(DISCORD_ANALYST_CHANNEL_ID)) if DISCORD_ANALYST_CHANNEL_ID else None
            if channel and hasattr(channel, "send"):
                try:
                    report = await post_json("/api/analyst/reports", {"period": "day", "source": "discord-scheduled"})
                    await channel.send(embed=report_embed(report))
                    last_posted_date = today
                except Exception as exc:
                    print(f"Daily analyst report failed: {exc}")
        await asyncio.sleep(60)


def dashboard_caption(data: dict) -> str:
    status_data = data.get("status", {})
    parsed = urlparse(DASHBOARD_URL)
    host_only = parsed.hostname in {"localhost", "127.0.0.1", None}
    note = "Host-only dashboard link" if host_only else "Dashboard link"
    return (
        f"Dashboard snapshot for **{status_data.get('server', 'main')}** "
        f"({status_data.get('onlinePlayers', 0)} online). "
        f"{note}: {DASHBOARD_URL}"
    )


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "Arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def card(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill="#ffffff", outline="#dbe3e0", width=2)


def panel(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str, heading_font: ImageFont.ImageFont) -> None:
    card(draw, x, y, w, h)
    draw.text((x + 24, y + 18), title, fill="#17202a", font=heading_font)
    draw.line((x, y + 62, x + w, y + 62), fill="#e5ebe8", width=2)


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    max_lines: int,
    *,
    fill: str,
    font: ImageFont.ImageFont,
) -> int:
    lines = wrap_text(draw, text, max_width, font)
    line_height = int(font.size * 1.35) if hasattr(font, "size") else 22
    clipped = lines[:max_lines]
    if len(lines) > max_lines and clipped:
        clipped[-1] = clipped[-1].rstrip(". ") + "..."
    for line in clipped:
        draw.text((x, y), line, fill=fill, font=font)
        y += line_height
    return y


def wrap_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, font: ImageFont.ImageFont) -> list[str]:
    text = " ".join(str(text).split())
    if not text:
        return [""]
    rough_width = max(12, max_width // 10)
    candidates = textwrap.wrap(text, width=rough_width, break_long_words=True)
    lines: list[str] = []
    for candidate in candidates:
        words = candidate.split()
        current = ""
        for word in words:
            attempt = f"{current} {word}".strip()
            if draw.textlength(attempt, font=font) <= max_width:
                current = attempt
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines or [text]


def fmt_time(value: object) -> str:
    if not value:
        return "none"
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return text[:24]


def main() -> None:
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not configured.")
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
