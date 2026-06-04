from app.schemas import AiAction


ALLOWED_ACTIONS = {"minecraft_chat", "minecraft_whisper", "minecraft_broadcast"}


def sanitize_ai_action(action: AiAction, fallback_target: str | None = None) -> AiAction:
    message = " ".join(action.response.strip().split())
    if not message:
        message = "I heard you, but I could not produce a useful response."
    if len(message) > 500:
        message = message[:497] + "..."

    target = action.target or fallback_target
    if action.action == "minecraft_whisper" and not target:
        action_name = "minecraft_chat"
    else:
        action_name = action.action

    if action_name not in ALLOWED_ACTIONS:
        action_name = "minecraft_chat"

    return AiAction(response=message, action=action_name, target=target)

