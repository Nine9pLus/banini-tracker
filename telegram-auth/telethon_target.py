"""Resolve TG_TARGET to a Telethon entity (basic groups vs channels need different peers)."""

from __future__ import annotations

from telethon import TelegramClient
from telethon.tl.types import PeerChannel, PeerChat

from telegram_outbound import parse_chat_id


async def resolve_send_entity(client: TelegramClient, target_raw: str):
    s = target_raw.strip()
    if not s.lstrip("-").isdigit():
        return s

    want = int(s)
    async for d in client.iter_dialogs(limit=200):
        if d.id == want:
            return d.entity

    # Fallback: numeric id alone is ambiguous (basic group vs channel vs user).
    if want < 0:
        t = str(want)
        if t.startswith("-100"):
            inner = int(t[4:])
            return await client.get_entity(PeerChannel(inner))
        # Legacy basic group: dialog id is negative; API uses PeerChat(positive)
        try:
            return await client.get_entity(PeerChat(abs(want)))
        except Exception:
            pass

    return parse_chat_id(target_raw)
