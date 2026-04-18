import asyncio
from datetime import datetime

from dotenv import load_dotenv
from telethon import TelegramClient

from login_account import require_env
from telegram_outbound import send_message_via_bot, use_bot_sender
from telethon_target import resolve_send_entity


async def main() -> None:
    load_dotenv()

    target_raw = require_env("TG_TARGET")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"[Test Notification] Telegram automation is working. ({now})"

    if use_bot_sender():
        token = require_env("TG_BOT_TOKEN")
        await asyncio.to_thread(send_message_via_bot, token, target_raw, message)
        print(f"Test message sent via Bot API to target: {target_raw}")
        return

    api_id = int(require_env("TG_API_ID"))
    api_hash = require_env("TG_API_HASH")

    async with TelegramClient("sessions/tg_account_a", api_id, api_hash) as client:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Account A session not authorized. Run login_account.py first."
            )

        entity = await resolve_send_entity(client, target_raw)
        await client.send_message(entity, message)
        print(f"Test message sent via user account to target: {target_raw}")


if __name__ == "__main__":
    asyncio.run(main())
