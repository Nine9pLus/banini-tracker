"""Send Telegram messages: Bot API (顯示為機器人) or Telethon user session."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def parse_chat_id(value: str) -> int | str:
    v = value.strip()
    return int(v) if v.lstrip("-").isdigit() else v


def bot_token_configured() -> bool:
    return bool(os.getenv("TG_BOT_TOKEN", "").strip())


def prefer_user_session() -> bool:
    """Set TG_PREFER_USER=1 to send via Telethon even if TG_BOT_TOKEN is set in .env."""
    v = os.getenv("TG_PREFER_USER", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def use_bot_sender() -> bool:
    if prefer_user_session():
        return False
    return bot_token_configured()


def send_message_via_bot(token: str, chat_id_raw: str, text: str, timeout_sec: int = 60) -> None:
    """POST https://api.telegram.org/bot<token>/sendMessage"""
    chat_id = parse_chat_id(chat_id_raw)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Bot API HTTP {e.code}: {err_body}") from e

    body = json.loads(raw)
    if not body.get("ok"):
        raise RuntimeError(f"Bot API error: {body}")
