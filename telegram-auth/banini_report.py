"""
Run banini skill scraper (../banini) and build a Telegram-sized report.
Analysis follows contrarian rules from banini SKILL.md (heuristic, no external LLM).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

TW = timezone(timedelta(hours=8))

# Minimal investment signal keywords (Traditional Chinese)
_INVEST_HINT = re.compile(
    r"(股|台股|ETF|期貨|選擇權|put|Put|PUT|空單|多單|停損|停利|買|賣|加碼|套牢|被套|看多|看空)"
)

# (keyword group, 她的動作 label, 反指標方向, default 信心)
_RULES: list[tuple[list[str], str, str, str]] = [
    (
        ["買入", "加碼", "買進", "買了", "進場", "買在", "加倉"],
        "買入/加碼",
        "可能跌",
        "中",
    ),
    (
        ["停損", "停損了", "賣出", "賣光", "認賠", "賣了", "出場", "砍倉"],
        "停損/賣出",
        "可能反彈",
        "中",
    ),
    (
        ["被套", "套牢", "還沒賣", "抱著", "死抱", "凹單", "持有中", "還在扛"],
        "被套/持有",
        "可能續跌",
        "中",
    ),
    (
        ["看多", "喊買", "看好", "買爆", "all in"],
        "看多",
        "可能跌",
        "中",
    ),
    (
        ["看空", "喊賣", "看衰", "不看好"],
        "看空",
        "可能漲",
        "中",
    ),
    (
        ["買put", "買 put", "Put", "空單", "放空", "做空"],
        "空單/買put",
        "可能飆漲",
        "高",
    ),
]


def _default_skill_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "banini"


def _win_python(skill_dir: Path) -> Path:
    return skill_dir / ".venv" / "Scripts" / "python.exe"


def _posix_python(skill_dir: Path) -> Path:
    return skill_dir / ".venv" / "bin" / "python"


def _python_exe(skill_dir: Path) -> Path:
    win = _win_python(skill_dir)
    if win.exists():
        return win
    posix = _posix_python(skill_dir)
    if posix.exists():
        return posix
    raise FileNotFoundError(
        f"Banini venv not found under {skill_dir}. "
        "Create venv and: pip install playwright parsel nested-lookup jmespath; playwright install chromium"
    )


def run_scrape(
    skill_dir: Path,
    username: str,
    max_scroll: int,
    timeout_sec: int = 300,
) -> list[dict]:
    script = skill_dir / "scripts" / "scrape_threads.py"
    if not script.is_file():
        raise FileNotFoundError(f"Missing scraper: {script}")

    python = _python_exe(skill_dir)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [str(python), str(script), username, str(max_scroll)],
        cwd=str(skill_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_sec,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"scrape_threads failed (exit {proc.returncode}): {proc.stderr[-2000:]}"
        )
    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    return json.loads(raw)


def _taipei_time(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=TW)


def _format_post_header(ts: int) -> str:
    dt = _taipei_time(ts)
    today = datetime.now(TW).date()
    d = dt.date()
    label = ""
    if d == today:
        label = "今天"
    elif d == today - timedelta(days=1):
        label = "昨天"
    else:
        label = f"{d.month:02d}/{d.day:02d}"
    return f"{label}（{dt:%Y/%m/%d %H:%M}）"


def _detect_rows(text: str) -> list[tuple[str, str, str, str]]:
    """Return rows: (標的粗估, 她的動作, 反指標方向, 信心)."""
    rows: list[tuple[str, str, str, str]] = []
    if not text.strip():
        return rows

    # 常見股票名稱白名單（優先匹配）
    _KNOWN = [
        "台積電", "台積", "聯發科", "鴻海", "聯電", "旺宏", "信驊", "廣達", "緯創",
        "美光", "輝達", "超微", "英偉達", "輝達", "AMD", "TSMC", "NVDA",
        "記憶體", "ABF", "光通訊",
    ]
    # 排除詞：這些出現在「股」前不算標的
    _EXCLUDE = {"類", "票", "市", "市場", "東", "民", "友", "神", "投資人", "散", "主力", "大"}

    ticker = ""
    for known in _KNOWN:
        if known in text:
            ticker = known
            break
    if not ticker:
        m = re.search(r"([\u4e00-\u9fff]{2,5})股(?!\s*市|票|東)", text)
        if m:
            candidate = m.group(1)
            # 末尾字不在排除詞中才採用
            if candidate[-1] not in _EXCLUDE and candidate not in _EXCLUDE:
                ticker = candidate

    for keywords, action, direction, conf in _RULES:
        if any(k.lower() in text.lower() if k.isascii() else k in text for k in keywords):
            label = ticker or "（未辨識標的）"
            rows.append((label, action, direction, conf))
    return rows


def _lantern_score(texts: list[str]) -> int:
    score = 5
    joined = "\n".join(texts)
    if re.search(r"(一定|保證|穩了|噴爆|all in|梭哈)", joined):
        score += 2
    if re.search(r"(崩潰|後悔|認輸|完蛋|哭)", joined):
        score += 1
    if re.search(r"(可能|不確定|再看看|觀望)", joined):
        score -= 1
    return max(1, min(10, score))


def build_report(
    posts: list[dict],
    username: str,
) -> str:
    if not posts:
        return (
            "【巴逆逆反指標】\n"
            f"資料來源：Threads @{username}\n"
            "本批無法取得貼文或與投資無關，略過標的分析。\n"
            "僅供娛樂參考，不構成投資建議。"
        )

    lines: list[str] = []
    lines.append("【巴逆逆反指標】")
    lines.append(f"分析時間：{datetime.now(TW):%Y-%m-%d %H:%M}（台北）")
    lines.append(f"資料來源：Threads @{username}，共 {len(posts)} 則")

    invest_posts: list[dict] = []
    for p in posts:
        t = p.get("text") or ""
        if _INVEST_HINT.search(t):
            invest_posts.append(p)

    if not invest_posts:
        lines.append("")
        lines.append("本批貼文與投資訊號關聯度低，略過標的分析。")
        lines.append("")
        lines.append("僅供娛樂參考，不構成投資建議。")
        return "\n".join(lines)

    all_rows: list[tuple[str, str, str, str]] = []
    excerpts: list[tuple[str, int]] = []
    for p in invest_posts[:12]:
        t = (p.get("text") or "").strip()
        if not t:
            continue
        likes = int(p.get("likes") or 0)
        hdr = _format_post_header(int(p.get("taken_at") or 0))
        for row in _detect_rows(t):
            all_rows.append(row)
        excerpt = t.replace("\n", " ").strip()
        if len(excerpt) > 120:
            excerpt = excerpt[:117] + "…"
        excerpts.append((excerpt, likes))

    has_sell = any("停損" in r[1] or "賣出" in r[1] for r in all_rows)
    has_buy = any("買入" in r[1] or "看多" in r[1] for r in all_rows)
    has_put = any("空單" in r[1] or "買put" in r[1] for r in all_rows)
    has_trapped = any("被套" in r[1] or "持有" in r[1] for r in all_rows)

    if has_sell:
        summary = "出現認賠/賣出語句，反指標常解讀為短線可能反彈。"
    elif has_buy:
        summary = "出現買入/看多語句，反指標常解讀為標的可能承壓。"
    elif has_put:
        summary = "出現空單/買put語句，反指標警示標的可能飆漲。"
    elif has_trapped:
        summary = "處於被套/持有狀態，反指標解讀為底部尚未確認，可能續跌。"
    else:
        summary = "語氣偏情緒化，反指標訊號需保留解讀空間。"

    # 動態綜合判讀（2-3句）
    judg_parts: list[str] = []
    unique_directions = list(dict.fromkeys(r[2] for r in all_rows))
    if unique_directions:
        dir_str = "、".join(unique_directions[:3])
        judg_parts.append(f"本批訊號方向：{dir_str}。")
    if has_sell and has_buy:
        judg_parts.append("同批出現買入與賣出，以最新操作為主要依據，方向分歧時信心降低。")
    elif has_sell:
        judg_parts.append("認賠出場通常是底部訊號，相關標的短線反彈機率提高。")
    elif has_buy:
        judg_parts.append("主動加碼/喊買是反指標警示，建議觀望或反向留意風險。")
    elif has_put:
        judg_parts.append("空單部位若為初建，反指標飆漲壓力最強；若已被套則壓力持續。")

    score = _lantern_score([(p.get("text") or "") for p in invest_posts])
    if score >= 7:
        judg_parts.append(f"冥燈指數偏高（{score}/10），篤定語氣加重反指標可信度。")
    elif score <= 3:
        judg_parts.append(f"冥燈指數偏低（{score}/10），語氣保守，反指標訊號強度有限。")
    if not judg_parts:
        judg_parts.append("以她的明確操作語句為主；若同一標的先買後賣，以最新敘述為準。")
    comprehensive = " ".join(judg_parts)

    lines.append("")
    lines.append(f"1) 一句話：{summary}")
    lines.append(f"2) 冥燈指數：{score}/10")
    lines.append("3) 標的（文字行，非表格）")
    if not all_rows:
        lines.append("（未能從關鍵字規則辨識出明確標的/動作）")
    else:
        seen: set[tuple[str, str, str]] = set()
        for sym, act, dire, conf in all_rows[:20]:
            key = (sym, act, dire)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"{sym} | {act} | {dire} | 信心 {conf}")

    lines.append("")
    lines.append(f"4) 綜合判讀：{comprehensive}")
    lines.append("")
    lines.append("─────────────────")
    lines.append("5) 原文節錄")
    for ex, lk in excerpts[:5]:
        lines.append(f"「{ex}」— 讚 {lk}")
    lines.append("")
    lines.append("僅供娛樂參考，不構成投資建議。")

    out = "\n".join(lines)
    if len(out) > 3900:
        out = out[:3890] + "\n…（已截斷）\n僅供娛樂參考，不構成投資建議。"
    return out


def run_banini_pipeline() -> str:
    load_dotenv()

    _raw = Path(os.getenv("BANINI_SKILL_DIR", str(_default_skill_dir()))).expanduser()
    skill_dir = (_raw if _raw.is_absolute() else Path(__file__).parent / _raw).resolve()
    username = os.getenv("BANINI_USERNAME", "banini31").strip() or "banini31"
    max_scroll = int(os.getenv("BANINI_MAX_SCROLL", "5"))

    posts = run_scrape(skill_dir, username, max_scroll)
    return build_report(posts, username)


if __name__ == "__main__":
    try:
        print(run_banini_pipeline())
    except Exception as e:
        print(f"[banini_report] error: {e}", file=sys.stderr)
        sys.exit(1)
