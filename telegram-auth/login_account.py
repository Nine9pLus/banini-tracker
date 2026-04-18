import os
from pathlib import Path

from telethon import TelegramClient
from dotenv import load_dotenv


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    load_dotenv()

    api_id = int(require_env("TG_API_ID"))
    api_hash = require_env("TG_API_HASH")
    phone = require_env("TG_A_PHONE")

    session_dir = Path("sessions")
    session_dir.mkdir(parents=True, exist_ok=True)
    session_name = session_dir / "tg_account_a"

    client = TelegramClient(str(session_name), api_id, api_hash)
    try:
        client.start(phone=phone)
        me = client.loop.run_until_complete(client.get_me())
        print(f"Login success: {me.first_name} (@{me.username or 'no_username'})")
        print(f"Session saved at: {session_name}.session")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
