"""Print chat_id from Bot getUpdates (after someone messages the bot or adds it to a group)."""

import json
import os
import urllib.request

from dotenv import load_dotenv

from login_account import require_env


def main() -> None:
    load_dotenv()
    token = require_env("TG_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.loads(r.read().decode())
    if not d.get("ok"):
        print(d)
        return
    seen: dict[int, tuple[str, str]] = {}
    for up in d.get("result") or []:
        msg = up.get("message") or up.get("channel_post") or up.get("edited_message")
        if not msg:
            continue
        ch = msg.get("chat") or {}
        cid = ch.get("id")
        if cid is None:
            continue
        title = (
            ch.get("title")
            or ch.get("username")
            or ch.get("first_name")
            or ""
        )
        typ = ch.get("type") or ""
        seen[int(cid)] = (typ, title)
    if not seen:
        print(
            "No updates. Add the bot to your group and send a message "
            "(or /start), then run this script again."
        )
        return
    print("Use one of these as TG_TARGET for Bot API:\n")
    for cid, (typ, title) in sorted(seen.items(), key=lambda x: x[0]):
        print(f"  chat_id={cid}  type={typ}  title={title}")


if __name__ == "__main__":
    main()
