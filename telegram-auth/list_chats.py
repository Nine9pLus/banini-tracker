import asyncio

from dotenv import load_dotenv
from telethon import TelegramClient

from login_account import require_env


async def main() -> None:
    load_dotenv()

    api_id = int(require_env("TG_API_ID"))
    api_hash = require_env("TG_API_HASH")

    async with TelegramClient("sessions/tg_account_a", api_id, api_hash) as client:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Account A session not authorized. Run login_account.py first."
            )

        print("Recent dialogs (use username or id as TG_TARGET):")
        async for dialog in client.iter_dialogs(limit=30):
            entity = dialog.entity
            username = getattr(entity, "username", None)
            target_hint = f"@{username}" if username else str(dialog.id)
            print(f"- {dialog.name} -> {target_hint}")


if __name__ == "__main__":
    asyncio.run(main())
