import json
import time
from dataclasses import dataclass

import httpx

from app.config import settings
from app.schemas import AiAction


@dataclass
class LlmResult:
    action: AiAction
    latency_ms: float
    raw_response: str


@dataclass
class TextLlmResult:
    text: str
    latency_ms: float
    raw_response: str


async def complete_ai_action(prompt: str, fallback_target: str | None = None) -> LlmResult:
    start = time.perf_counter()
    if settings.llm_provider == "mock":
        action = AiAction(
            response="I am online. Ask me about server rules, builds, players, or survival help.",
            action="minecraft_whisper" if fallback_target else "minecraft_chat",
            target=fallback_target,
        )
        return LlmResult(action=action, latency_ms=(time.perf_counter() - start) * 1000, raw_response=action.model_dump_json())

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": "Return only valid JSON. Do not include markdown."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{settings.llm_base_url.rstrip('/')}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:240]
        message = "I could not reach my Groq brain. Check the API key and model in the server .env file."
        action = AiAction(response=message, action="minecraft_whisper" if fallback_target else "minecraft_chat", target=fallback_target)
        return LlmResult(action=action, latency_ms=(time.perf_counter() - start) * 1000, raw_response=detail)
    except httpx.RequestError as exc:
        message = "I could not connect to the LLM provider. The backend is still running."
        action = AiAction(response=message, action="minecraft_whisper" if fallback_target else "minecraft_chat", target=fallback_target)
        return LlmResult(action=action, latency_ms=(time.perf_counter() - start) * 1000, raw_response=str(exc))
    content = body["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
        action = AiAction(**parsed)
    except Exception:
        action = AiAction(response=content.strip(), action="minecraft_whisper" if fallback_target else "minecraft_chat", target=fallback_target)
    return LlmResult(action=action, latency_ms=(time.perf_counter() - start) * 1000, raw_response=content)


async def complete_text(prompt: str) -> TextLlmResult:
    start = time.perf_counter()
    if settings.llm_provider == "mock":
        text = "Nothing much happened yet. The server is alive, which is already more than some bases can say."
        return TextLlmResult(text=text, latency_ms=(time.perf_counter() - start) * 1000, raw_response=text)

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": "Write plain text. Do not use markdown tables."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.55,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{settings.llm_base_url.rstrip('/')}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:240]
        text = "The analyst tried to think, hit the LLM API wall, and face-planted. Check the Groq key/model."
        return TextLlmResult(text=text, latency_ms=(time.perf_counter() - start) * 1000, raw_response=detail)
    except httpx.RequestError as exc:
        text = "The analyst could not reach the LLM provider. Backend is alive; the brain cable is not."
        return TextLlmResult(text=text, latency_ms=(time.perf_counter() - start) * 1000, raw_response=str(exc))

    content = body["choices"][0]["message"]["content"].strip()
    return TextLlmResult(text=content, latency_ms=(time.perf_counter() - start) * 1000, raw_response=content)
