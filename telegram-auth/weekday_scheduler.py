import asyncio
import os
import traceback
from datetime import datetime, timedelta

# Windows: child scraper + console output UTF-8
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from dotenv import load_dotenv
from telethon import TelegramClient

from banini_report import run_banini_pipeline
from login_account import require_env
from telegram_outbound import send_message_via_bot, use_bot_sender
from telethon_target import resolve_send_entity


def parse_schedule_times(value: str) -> list[tuple[int, int]]:
    parsed: list[tuple[int, int]] = []
    for item in value.split(","):
        token = item.strip()
        if not token:
            continue
        hour_str, minute_str = token.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid schedule time: {token}")
        parsed.append((hour, minute))
    if not parsed:
        raise ValueError("TG_SCHEDULE_TIMES is empty.")
    return sorted(set(parsed))


def next_run_at(now: datetime, times: list[tuple[int, int]]) -> datetime:
    # Weekday: Monday=0 ... Friday=4
    for day_offset in range(0, 8):
        candidate_date = (now + timedelta(days=day_offset)).date()
        if candidate_date.weekday() >= 5:
            continue
        for hour, minute in times:
            candidate = datetime.combine(
                candidate_date, datetime.min.time()
            ).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate > now:
                return candidate
    raise RuntimeError("Unable to compute next run time.")


async def main() -> None:
    load_dotenv()

    target_raw = require_env("TG_TARGET")
    schedule_raw = os.getenv("TG_SCHEDULE_TIMES", "09:00,12:30")
    schedule_times = parse_schedule_times(schedule_raw)

    dry_run = os.getenv("TG_DRY_RUN", "").strip() == "1"
    once_run = os.getenv("TG_ONCE_RUN", "").strip() == "1"
    use_bot = use_bot_sender()
    bot_token = os.getenv("TG_BOT_TOKEN", "").strip() if use_bot else ""

    async def run_once_send(report: str) -> None:
        if use_bot:
            await asyncio.to_thread(send_message_via_bot, bot_token, target_raw, report)
        else:
            entity = await resolve_send_entity(client, target_raw)
            await client.send_message(entity, report)

    async def run_once() -> None:
        sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            report = await asyncio.to_thread(run_banini_pipeline)
        except Exception:
            err = traceback.format_exc()[-3500:]
            report = f"[banini 執行失敗] {sent_at}\n{err}"
        if len(report) > 4096:
            report = report[:4080] + "\n…（已截斷）"
        await run_once_send(report)
        print(f"Sent banini report at {sent_at}")

    async def drive() -> None:
        sender = "Bot API (TG_BOT_TOKEN)" if use_bot else "Telethon user session"
        print(
            "Weekday scheduler started (banini scrape + Telegram). "
            f"Sender={sender}, Target={target_raw}, "
            f"Times={', '.join(f'{h:02d}:{m:02d}' for h, m in schedule_times)}"
        )

        if once_run:
            if dry_run:
                print("TG_ONCE_RUN=1 + TG_DRY_RUN=1: no send.")
                return
            await run_once()
            return

        while True:
            now = datetime.now()
            run_at = next_run_at(now, schedule_times)
            wait_seconds = max(0.0, (run_at - now).total_seconds())
            print(f"Next run at {run_at:%Y-%m-%d %H:%M:%S}")

            if dry_run:
                print("Dry run mode enabled (TG_DRY_RUN=1). Exiting without sending.")
                return

            await asyncio.sleep(wait_seconds)

            await run_once()

    if use_bot:
        await drive()
        return

    api_id = int(require_env("TG_API_ID"))
    api_hash = require_env("TG_API_HASH")

    async with TelegramClient("sessions/tg_account_a", api_id, api_hash) as client:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Account A session not authorized. Run login_account.py first."
            )
        await drive()


if __name__ == "__main__":
    asyncio.run(main())
