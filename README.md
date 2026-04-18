# banini-tracker

巴逆逆（Threads `@banini31`）反指標追蹤器 — Windows 個人化整合版。

本機 Playwright 爬 Threads → Python 啟發式規則做反指標分析 → 透過 Telegram Bot API 推到手機。**不需要 API key、不需要付費爬蟲服務、不需要 Claude 在線**。

## 致謝

本 repo 整合並改寫自下列三個原始專案：

- **[cablate/banini-tracker](https://github.com/cablate/banini-tracker)** — 原始概念與反指標規則
- **[KerberosClaw/kc_ai_skills/banini](https://github.com/KerberosClaw/kc_ai_skills/tree/main/banini)** — Threads 爬蟲（Playwright 攔截 GraphQL）與 skill 化
- **[KerberosClaw/kc_ai_skills/skill-cron](https://github.com/KerberosClaw/kc_ai_skills/tree/main/skill-cron)** — 排程設計概念

差異點：把排程從 crontab + Claude CLI 改為 Windows Task Scheduler + 純 Python（不依賴 Claude），更適合 Windows 桌機常駐使用。

## 結構

```
banini-tracker/
├── banini/              # Claude Code skill：Threads 爬蟲 + 反指標分析
│   ├── SKILL.md
│   ├── scripts/
│   │   └── scrape_threads.py
│   └── docs/
└── telegram-auth/       # 獨立 Python 排程器：定時跑 banini → 推 Telegram
    ├── weekday_scheduler.py
    ├── banini_report.py
    ├── telegram_outbound.py
    ├── register_tasks.ps1
    └── .env.example
```

兩個模組相對獨立：

- `banini/` 可單獨安裝為 [Claude Code](https://docs.claude.com/en/docs/claude-code) skill，在對話中打 `/banini` 互動觸發
- `telegram-auth/` 是純 Python 排程，會以相對路徑 `../banini` 直接呼叫 skill 內的爬蟲腳本，**整個流程繞過 Claude，自己跑分析**

## 安裝

### 1. Clone

```bash
git clone https://github.com/Nine9pLus/banini-tracker.git
cd banini-tracker
```

### 2. 建立兩個獨立 venv

`banini/` 與 `telegram-auth/` 各自有獨立 Python 環境，互不相干。

```bash
# banini 爬蟲環境（Playwright + Threads 解析）
python -m venv banini/.venv
banini/.venv/Scripts/pip install playwright parsel nested-lookup jmespath
banini/.venv/Scripts/python -m playwright install chromium

# telegram-auth 排程與發送環境
python -m venv telegram-auth/.venv
telegram-auth/.venv/Scripts/pip install telethon python-dotenv requests
```

### 3. 設定 Telegram Bot

1. Telegram 找 [@BotFather](https://t.me/BotFather)，發 `/newbot`，取得 `TG_BOT_TOKEN`
2. 把 Bot 加進你的目標聊天室（個人對話、群組或頻道）
3. Telegram 找 [@userinfobot](https://t.me/userinfobot)，發 `/start`，取得個人 Chat ID（群組 ID 為負數，可用 `list_chats.py` 取得）

### 4. 填 `.env`

```bash
cp telegram-auth/.env.example telegram-auth/.env
```

編輯 `telegram-auth/.env`：

```env
TG_API_ID=12345678                    # 從 https://my.telegram.org/apps 取得
TG_API_HASH=your_api_hash_here
TG_A_PHONE=+8869xxxxxxxx              # 你的 Telegram 手機號（含 +886）
TG_TARGET=-1001234567890              # 群組/頻道 ID（負數），或個人聊天 ID
TG_BOT_TOKEN=123456:ABC...            # 從 @BotFather 取得
TG_SCHEDULE_TIMES=09:20,12:20         # 僅在常駐模式生效；用 Task Scheduler 時忽略
BANINI_SKILL_DIR=../banini            # 預設值，通常不用改
BANINI_USERNAME=banini31              # 追蹤目標 Threads 帳號
BANINI_MAX_SCROLL=5
```

### 5. 首次測試

```bash
cd telegram-auth
.venv/Scripts/python send_test_notification.py    # 確認 Bot 能發訊息
.venv/Scripts/python banini_report.py             # 確認爬蟲 + 分析能跑
```

## 自動排程（Windows Task Scheduler）

推薦用 Task Scheduler，每個觸發時段獨立跑一次，**不需要常駐終端機**。

### 註冊

```powershell
cd telegram-auth
powershell -ExecutionPolicy Bypass -File .\register_tasks.ps1
```

預設建立兩個任務：`BaniniTracker_0920`、`BaniniTracker_1220`，週一至週五觸發。修改時間請編輯 `register_tasks.ps1` 內的 `$Schedules` 區塊後重跑腳本。

### 驗證

```powershell
Get-ScheduledTask -TaskName 'BaniniTracker_*' | Format-Table TaskName, State, @{n='NextRun';e={(Get-ScheduledTaskInfo $_).NextRunTime}}

Start-ScheduledTask -TaskName 'BaniniTracker_0920'   # 立刻觸發測試
Get-Content .\logs\task_scheduler.log -Tail 50       # 查 log
```

### 限制

- 電腦關機時段內的排程不會跑（但 `-StartWhenAvailable` 設定會在開機後自動補跑當日錯過的任務）
- 必須登入 Windows session（鎖定螢幕沒關係）
- 搬移 `telegram-auth/` 資料夾後需重跑 `register_tasks.ps1` 更新絕對路徑

### 移除

```powershell
Unregister-ScheduledTask -TaskName 'BaniniTracker_0920' -Confirm:$false
Unregister-ScheduledTask -TaskName 'BaniniTracker_1220' -Confirm:$false
```

## 替代方案：常駐 Python 排程

若不用 Task Scheduler，可直接跑 `weekday_scheduler.py` 當作常駐程式，由它自己看 `TG_SCHEDULE_TIMES` 等待時間。

```bash
cd telegram-auth
.venv/Scripts/python weekday_scheduler.py
```

缺點：終端機關閉、登出、重開機都會中斷，需另外處理。

## 反指標規則

詳見 [banini/SKILL.md](banini/SKILL.md#反指標核心規則)。摘要：

| 她的狀態 | 反指標解讀 |
|---|---|
| 買入/加碼 | 該標的可能下跌 |
| 持有/被套（還沒賣） | 可能繼續跌 |
| 停損/賣出 | 可能反彈 |
| 看多 | 可能跌 |
| 看空 | 可能漲 |
| 空單/買 put | 可能飆漲 |

`telegram-auth/banini_report.py` 用啟發式關鍵字規則自動分類；若想要更細緻的判讀，可改用 Claude skill 的 `/banini` 互動模式（由 Claude 直接讀貼文做語意分析）。

## 免責聲明

本工具僅供娛樂與學術目的。所有輸出**不構成任何投資建議**。實際投資決策請自行負責。
