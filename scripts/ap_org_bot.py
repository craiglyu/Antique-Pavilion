"""
ap_org_bot.py — 吉寶軒 Multi-Agent ORG Discord Bot  v1.2
架構：Thor MultiAgent ORG V10，適配 Antique Pavilion 專案。

頻道路由：
  #ap-pm        → PM Agent (via !agenda)
  #ap-web-design → Designer Agent (自動)
  #ap-web-dev    → Dev Agent (自動)
  #ap-marketing  → Marketing Agent (自動)
  #ap-feedback   → Feedback PM（定時彙整 → Claude 分析 → 提案 Embed）

Feedback PM 流程：
  Craig / 夥伴隨時在 #ap-feedback 發佈 UX 意見
  → 每日 11:00 / 20:00（台北時間）自動彙整
  → Claude Sonnet 輸出 P0–P3 改善提案 Embed
  → Craig [✅ 批准] → #ap-web-dev 自動建立任務 Embed
  → Craig [❌ 否決] → 歸檔至 feedback_state.json
  → 3 天未回應 → 自動標記 expired（每日 00:30 掃描）

Claude 調用方式：
  Claude Code CLI (claude -p headless)，走 Claude MAX/Pro 訂閱，
  不需要 Anthropic API Key，不按 token 額外計費。

Run: python -u scripts/ap_org_bot.py
"""

import asyncio
import json
import logging
import os
import ssl as _ssl
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytz

# Windows 企業環境 SSL patch（防毒注入自簽憑證）
_orig_ssl_ctx = _ssl.create_default_context
def _no_verify_ssl_ctx(*args, **kwargs):
    ctx = _orig_ssl_ctx(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    return ctx
_ssl.create_default_context = _no_verify_ssl_ctx

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import discord
from discord import app_commands, ui
from discord.ext import commands

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env.antique"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ap_org_bot")

# ── Env loader ───────────────────────────────────────────────────────────────

def _load_env(env_file: Path) -> dict:
    env = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if v})
    return env

_ENV = _load_env(ENV_FILE)

def _env(key: str, default: str = "") -> str:
    return _ENV.get(key, os.environ.get(key, default))

# ── 頻道 ID 對應 ──────────────────────────────────────────────────────────────

CHANNEL_PM        = int(_env("DISCORD_CHANNEL_AP_PM",        "1495280076688719942"))
CHANNEL_DESIGN    = int(_env("DISCORD_CHANNEL_AP_DESIGN",    "1495280308143259708"))
CHANNEL_DEV       = int(_env("DISCORD_CHANNEL_AP_DEV",       "1495280247590097059"))
CHANNEL_MARKETING = int(_env("DISCORD_CHANNEL_AP_MARKETING", "1495678294039990312"))
CHANNEL_FEEDBACK  = int(_env("DISCORD_CHANNEL_AP_FEEDBACK",  "1497066777677398026"))

# ── Feedback 系統設定 ─────────────────────────────────────────────────────────

# 授權用戶：可發佈 Feedback、批准/否決提案
ALLOWED_USER_IDS = {
    _env("DISCORD_CRAIG_USER_ID", "566565645483769863"),  # Craig
    "1495302135112401067",                                 # 協作夥伴
}

MONTHLY_CALL_LIMIT = 120      # 每月最多呼叫 claude CLI 次數（監控用，非硬計費）
CLAUDE_MODEL       = "claude-sonnet-4-6"
CLAUDE_CLI_TIMEOUT = 120      # 秒

POLL_HOUR_1           = 11    # 每日第一次 Poll（台北時間）
POLL_HOUR_2           = 20    # 每日第二次 Poll（台北時間）
PROPOSAL_EXPIRY_DAYS  = 3     # 提案等待 Craig 批准的天數

TAIPEI_TZ  = pytz.timezone("Asia/Taipei")
STATE_FILE = PROJECT_ROOT / "feedback_state.json"

# ── Subprocess helpers ────────────────────────────────────────────────────────

def _build_claude_cmd(claude_args: list[str]) -> list[str]:
    import platform
    if platform.system() == "Windows":
        inner = " ".join(f'"{a}"' if " " in a else a for a in claude_args)
        return ["wsl", "bash", "-c", inner]
    return claude_args


def _build_headless_cmd() -> list[str]:
    """claude -p headless 單次回應（Feedback PM 分析用）"""
    args = ["claude", "-p", "--model", CLAUDE_MODEL, "--max-turns", "1"]
    import platform
    if platform.system() == "Windows":
        return ["wsl", "bash", "-c", " ".join(args)]
    return args


async def _run_claude_cli(prompt: str, timeout: float = CLAUDE_CLI_TIMEOUT) -> str:
    """執行 claude -p headless，prompt 透過 stdin 傳入，走 MAX/Pro 訂閱。"""
    cmd = _build_headless_cmd()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(input=prompt.encode("utf-8")), timeout=timeout
    )
    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()
    if err:
        log.debug("[CLI] stderr: %s", err[:300])
    if not out:
        raise RuntimeError("claude CLI 無回應（stdout 為空）")
    return out


def _split_for_discord(text: str, limit: int = 1900) -> list[str]:
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text); break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1: split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks

# ── Feedback 狀態管理（JSON 持久化）─────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "last_feedback_message_id": None,
        "monthly_calls": 0,
        "month_key": "",
        "proposals": {}
    }


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _reset_monthly_counter_if_needed(state: dict) -> dict:
    now_key = datetime.now(TAIPEI_TZ).strftime("%Y-%m")
    if state.get("month_key") != now_key:
        state["monthly_calls"] = 0
        state["month_key"] = now_key
    return state

# ── Feedback PM — Claude Sonnet 分析提案 ─────────────────────────────────────

PM_SYSTEM_PROMPT = """你是吉寶軒（Antique Digital Pavilion）的專案 PM Claude Sonnet。

你的任務：
1. 閱讀 #ap-feedback 頻道中 Craig 與協作夥伴的 UX 反饋意見
2. 分析問題，提出具體可執行的改善提案
3. 以嚴格 JSON 格式輸出（不加任何 markdown 包裝）

【專案技術約束 — 不可違反】
- 前端：純 HTML / CSS / JS，禁止引入 React / Vue / Tailwind 等框架
- 後端：Google Apps Script (GAS)
- Google Sheets 欄位結構已凍結，不可新增 / 修改欄位
- 不可建議「遷移平台」「引入框架」等大規模架構變更
- 每個提案必須在 1–3 天內可由一人完成

【輸出格式 — 嚴格遵守，只輸出 JSON 陣列】
[
  {
    "priority": "P0",
    "title": "簡短標題（20 字內）",
    "problem": "問題描述（2–3 句）",
    "solution": "具體解決方案（步驟說明，3–5 句）",
    "effort": "1天/2天/3天",
    "category": "視覺設計/互動體驗/效能/文案/功能"
  }
]

優先級定義：
- P0 = 嚴重影響使用（崩版、功能失效）
- P1 = 明顯影響體驗（排版、字體問題）
- P2 = 一般改善（視覺優化、互動細節）
- P3 = 加分項目（動畫、微互動）

每次輸出 2–5 個提案，依優先級排序。只輸出 JSON，禁止任何前後說明文字。"""


async def generate_proposals(feedback_messages: list[dict]) -> list[dict]:
    """呼叫 Claude Code CLI 彙整反饋，回傳提案列表。"""
    state = load_state()
    state = _reset_monthly_counter_if_needed(state)

    if state["monthly_calls"] >= MONTHLY_CALL_LIMIT:
        log.warning("[PM] 月呼叫次數 %d 已達上限 %d，跳過",
                    state["monthly_calls"], MONTHLY_CALL_LIMIT)
        return []

    feedback_text = "\n".join(
        f"[{m['time']}] {m['author']}: {m['content']}"
        for m in feedback_messages
    )

    full_prompt = (
        f"{PM_SYSTEM_PROMPT}\n\n"
        "---\n\n"
        "以下是 #ap-feedback 頻道中的最新 UX 反饋意見：\n\n"
        f"{feedback_text}\n\n"
        "請根據以上反饋，分析問題並提出改善提案。只輸出 JSON 陣列。"
    )

    raw = ""
    try:
        raw = await _run_claude_cli(full_prompt)
        state["monthly_calls"] = state.get("monthly_calls", 0) + 1
        save_state(state)
        log.info("[PM] ✅ CLI 呼叫完成（本月第 %d 次）", state["monthly_calls"])

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:].strip()

        proposals = json.loads(raw)
        return proposals if isinstance(proposals, list) else []

    except json.JSONDecodeError as e:
        log.error("[PM] JSON 解析失敗: %s\n原始輸出: %s", e, raw[:300])
        return []
    except RuntimeError as e:
        log.error("[PM] CLI 錯誤: %s", e)
        return []
    except Exception as e:
        log.error("[PM] 未預期錯誤: %s", e, exc_info=True)
        return []

# ── Feedback Embed 建構 ───────────────────────────────────────────────────────

PRIORITY_COLORS = {
    "P0": 0xDC2626,   # 紅 — 阻塞
    "P1": 0xD97706,   # 橙 — 重要
    "P2": 0xB8960C,   # 金 — 一般（吉寶軒品牌色）
    "P3": 0x6B7280,   # 灰 — 加分
}


def build_proposal_embed(proposal: dict, idx: int, total: int, poll_id: str) -> discord.Embed:
    priority = proposal.get("priority", "P2")
    embed = discord.Embed(
        title     = f"【{priority}】{proposal.get('title', '改善提案')}",
        color     = PRIORITY_COLORS.get(priority, 0xB8960C),
        timestamp = datetime.now(timezone.utc)
    )
    embed.add_field(name="🔍 問題",     value=proposal.get("problem",  "—"), inline=False)
    embed.add_field(name="💡 解決方案", value=proposal.get("solution", "—"), inline=False)
    embed.add_field(name="⏱ 工時",     value=proposal.get("effort",   "—"), inline=True)
    embed.add_field(name="📂 類別",     value=proposal.get("category", "—"), inline=True)
    embed.set_footer(text=f"提案 {idx}/{total} · {poll_id} · 3 天內無回應自動失效")
    return embed


def build_approved_task_embed(proposal: dict, approved_by: str) -> discord.Embed:
    priority = proposal.get("priority", "P2")
    embed = discord.Embed(
        title       = f"📌 新任務：{proposal.get('title', '開發任務')}",
        description = f"**來源**：#ap-feedback 批准提案 [{priority}]",
        color       = 0x2D7D46,
        timestamp   = datetime.now(timezone.utc)
    )
    embed.add_field(name="問題描述", value=proposal.get("problem",  "—"), inline=False)
    embed.add_field(name="實作方向", value=proposal.get("solution", "—"), inline=False)
    embed.add_field(name="預估工時", value=proposal.get("effort",   "—"), inline=True)
    embed.add_field(name="類別",     value=proposal.get("category", "—"), inline=True)
    embed.set_footer(text=f"由 {approved_by} 批准 · 自動建立於 #ap-web-dev")
    return embed

# ── 單一提案 Button View ──────────────────────────────────────────────────────

class SingleProposalView(ui.View):
    """每個提案有自己的 [✅ 批准執行] / [❌ 否決] 按鈕對"""

    def __init__(self, proposal: dict, poll_id: str, proposal_idx: int):
        super().__init__(timeout=259200)   # 3 天 = 72h × 3600s
        self.proposal     = proposal
        self.poll_id      = poll_id
        self.proposal_idx = proposal_idx
        self.decided      = False

    async def _handle(self, interaction: discord.Interaction, approved: bool):
        if str(interaction.user.id) not in ALLOWED_USER_IDS:
            await interaction.response.send_message("只有授權用戶可以批准或否決。", ephemeral=True)
            return
        if self.decided:
            await interaction.response.send_message("此提案已處理。", ephemeral=True)
            return

        self.decided = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        if approved:
            web_dev_ch = bot.get_channel(CHANNEL_DEV)
            if web_dev_ch:
                task_embed = build_approved_task_embed(
                    self.proposal, interaction.user.display_name
                )
                await web_dev_ch.send(embed=task_embed)

                # ── 自動執行路由 ──────────────────────────────────────
                # 前端類（視覺設計/互動體驗）→ 直接修改 index.html + git push
                # GAS/功能類 → 產出代碼方案，Craig 手動貼入 GAS 重新部署
                category = self.proposal.get("category", "")
                if category in FRONTEND_CATEGORIES:
                    asyncio.create_task(
                        _spawn_auto_execute_task(self.proposal, self.poll_id, web_dev_ch)
                    )
                else:
                    asyncio.create_task(
                        _spawn_auto_gas_task(self.proposal, self.poll_id, web_dev_ch)
                    )

            await interaction.followup.send(
                f"✅ 批准 [{self.proposal.get('priority')}] "
                f"**{self.proposal.get('title')}**\n"
                f"任務已建立至 #ap-web-dev，Dev Agent 自動執行中 ⚙️",
                ephemeral=True
            )
            log.info("[Feedback] ✅ 批准: %s", self.proposal.get("title"))
        else:
            await interaction.followup.send(
                f"❌ 已否決 [{self.proposal.get('priority')}] "
                f"**{self.proposal.get('title')}**",
                ephemeral=True
            )
            log.info("[Feedback] ❌ 否決: %s", self.proposal.get("title"))

        state = load_state()
        polls = state.get("proposals", {})
        if self.poll_id in polls:
            items = polls[self.poll_id].get("items", [])
            if self.proposal_idx < len(items):
                items[self.proposal_idx]["status"]     = "approved" if approved else "vetoed"
                items[self.proposal_idx]["decided_by"] = str(interaction.user)
                items[self.proposal_idx]["decided_at"] = datetime.now(TAIPEI_TZ).isoformat()
            save_state(state)

    @ui.button(label="✅ 批准執行", style=discord.ButtonStyle.success)
    async def approve_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle(interaction, True)

    @ui.button(label="❌ 否決", style=discord.ButtonStyle.danger)
    async def veto_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle(interaction, False)

# ── Feedback 排程任務 ─────────────────────────────────────────────────────────

async def run_feedback_poll():
    """彙整 #ap-feedback 訊息 → Claude PM → 發佈提案 Embed"""
    feedback_ch = bot.get_channel(CHANNEL_FEEDBACK)
    if not feedback_ch:
        log.error("[Poll] 找不到 #ap-feedback (ID=%s)", CHANNEL_FEEDBACK)
        return

    state       = load_state()
    last_id_str = state.get("last_feedback_message_id")

    messages = []
    async for msg in feedback_ch.history(limit=100, oldest_first=True):
        if msg.author.bot:
            continue
        if str(msg.author.id) not in ALLOWED_USER_IDS:
            continue
        if last_id_str and msg.id <= int(last_id_str):
            continue
        messages.append({
            "time":    msg.created_at.astimezone(TAIPEI_TZ).strftime("%m/%d %H:%M"),
            "author":  msg.author.display_name,
            "content": msg.content[:500]
        })

    if not messages:
        log.info("[Poll] 無新反饋訊息，跳過")
        return

    async for msg in feedback_ch.history(limit=1):
        state["last_feedback_message_id"] = str(msg.id)

    log.info("[Poll] 收集到 %d 則反饋，呼叫 Claude PM...", len(messages))
    proposals = await generate_proposals(messages)

    if not proposals:
        log.warning("[Poll] Claude PM 未產生任何提案")
        return

    poll_id = f"poll-{datetime.now(TAIPEI_TZ).strftime('%Y%m%d-%H%M')}"

    state.setdefault("proposals", {})[poll_id] = {
        "created_at": datetime.now(TAIPEI_TZ).isoformat(),
        "items": [{"status": "pending", **p} for p in proposals]
    }
    save_state(state)

    now_str = datetime.now(TAIPEI_TZ).strftime("%m/%d %H:%M")
    header  = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **PM Claude — UX 改善提案** `{poll_id}`\n"
        f"根據 **{len(messages)}** 則反饋分析 · {now_str}（台北時間）\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await feedback_ch.send(header)

    for i, proposal in enumerate(proposals):
        embed = build_proposal_embed(proposal, i + 1, len(proposals), poll_id)
        view  = SingleProposalView(proposal, poll_id, i)
        await feedback_ch.send(embed=embed, view=view)

    log.info("[Poll] ✅ 發佈 %d 個提案 (poll_id=%s)", len(proposals), poll_id)


async def check_expired_proposals():
    """每日 00:30 掃描，標記超過 3 天未回應的提案為 expired"""
    state   = load_state()
    now     = datetime.now(TAIPEI_TZ)
    changed = False

    for poll_id, poll_data in state.get("proposals", {}).items():
        try:
            created_at = datetime.fromisoformat(poll_data.get("created_at", ""))
            if created_at.tzinfo is None:
                created_at = TAIPEI_TZ.localize(created_at)
        except (ValueError, TypeError):
            continue

        if (now - created_at) > timedelta(days=PROPOSAL_EXPIRY_DAYS):
            for item in poll_data.get("items", []):
                if item.get("status") == "pending":
                    item["status"] = "expired"
                    changed        = True

    if changed:
        save_state(state)
        log.info("[Expiry] 已標記過期提案")

# ── Opus 設計仲裁 ──────────────────────────────────────────────────────────────

def _parse_opus_items(text: str) -> tuple[str, list[str]]:
    """從 Agent 回應中拆出 OPUS_ESCALATE: 區塊（設計仲裁用）。"""
    marker = "OPUS_ESCALATE:"
    if marker not in text:
        return text, []
    parts = text.split(marker, 1)
    clean = parts[0].strip()
    items = [l.strip().lstrip("-•·").strip() for l in parts[1].strip().splitlines() if l.strip()]
    return clean, items[:3]

class DesignEscalateView(discord.ui.View):
    """Craig 點擊後觸發 Opus 設計仲裁（DD-XXX）。"""
    def __init__(self, items: list[str], ticket_id: str, channel):
        super().__init__(timeout=7200)
        self.channel = channel
        for item in items:
            btn = discord.ui.Button(label=f"🎨 {item[:45]}", style=discord.ButtonStyle.primary)
            btn.callback = self._make_callback(item, ticket_id)
            self.add_item(btn)

    def _make_callback(self, item: str, ticket_id: str):
        async def callback(interaction: discord.Interaction):
            craig_id = _env("DISCORD_CRAIG_USER_ID")
            if craig_id and str(interaction.user.id) != craig_id:
                await interaction.response.send_message("只有 Craig 可以送審設計決策。", ephemeral=True)
                return
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
            dd_id = f"DD-{time.strftime('%Y%m%d-%H%M%S')}"
            await interaction.followup.send(f"📦 `{dd_id}` — **{item}**\n_Sonnet 正在起草設計仲裁包..._")
            asyncio.create_task(_spawn_opus_design_ruling(item, dd_id, self.channel))
        return callback

async def _spawn_opus_design_ruling(topic: str, dd_id: str, channel):
    """Phase 1: Sonnet 起草 DD 包 → Phase 2: Opus 設計仲裁。"""
    writer_prompt = (
        f"You are a design researcher for 吉寶軒 (Jibao Xuan), a high-luxury Chinese antique gallery.\n\n"
        f"Write a complete Design Decision Package (DD) in Traditional Chinese with English technical terms.\n\n"
        f"ticket_id: {dd_id}\n"
        f"Design question: {topic}\n\n"
        f"Steps:\n"
        f"1. Read .claude/commands/taste-skill.md — understand brand constraints\n"
        f"2. Read .claude/commands/impeccable-audit.md — understand quality dimensions\n"
        f"3. Read Publish/index.html — understand current implementation\n"
        f"4. Output a DD package with:\n"
        f"   - 問題背景 (2-3 sentences)\n"
        f"   - 方案 A (具體 CSS/HTML 實作，含優缺點)\n"
        f"   - 方案 B (替代方案，含優缺點)\n"
        f"   - 品牌相容性分析 (Sotheby's/Christie's 標準)\n"
        f"   - 建議 (Sonnet 的偏好方向)\n\n"
        f"Output only the DD markdown body, no other content."
    )
    pkg_path = PROJECT_ROOT / "memory" / "opus_inbox" / f"{dd_id}.md"
    pkg_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = _build_claude_cmd([
        "claude", "-p",
        "--model", "claude-sonnet-4-6",
        "--allowedTools", "Read,Grep,Glob",
        "--max-turns", "10",
    ])
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=writer_prompt.encode("utf-8")), timeout=300
        )
        pkg_content = stdout.decode("utf-8", errors="replace").strip()
        if not pkg_content:
            err_detail = stderr.decode("utf-8", errors="replace")[:300]
            await channel.send(f"❌ `{dd_id}` Sonnet 未產生 DD 包\nstderr: ```{err_detail}```")
            return
    except asyncio.TimeoutError:
        await channel.send(f"⚠️ `{dd_id}` DD 包起草逾時（>5 分鐘）")
        return
    except Exception as e:
        await channel.send(f"❌ `{dd_id}` DD 包起草失敗：{e}")
        return

    pkg_path.write_text(pkg_content, encoding="utf-8")
    await channel.send("🎨 設計 DD 包備妥 → 送交 Opus 仲裁，請稍候（約 2–5 分鐘）...")

    sys_file = PROJECT_ROOT / "config" / "opus_design_system_prompt.txt"
    opus_system = sys_file.read_text(encoding="utf-8") if sys_file.exists() else (
        "You are a luxury design director for a high-end Chinese antique gallery. "
        "Your aesthetic references are Sotheby's Asia, Christie's Hong Kong, China Guardian (中國嘉德), "
        "and the National Palace Museum (故宮). "
        "Make decisive design rulings. Do not hedge. Do not suggest more options — pick one and explain why."
    )

    opus_args = [
        "claude", "-p", pkg_content,
        "--model", "claude-opus-4-7",
        "--allowedTools", "Read,Grep,Glob",
        "--output-format", "json",
        "--max-turns", "5",
    ]
    cmd = _build_claude_cmd(opus_args)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
        raw = stdout.decode("utf-8", errors="replace").strip()
    except asyncio.TimeoutError:
        await channel.send(f"⚠️ `{dd_id}` Opus 逾時（>10 分鐘）")
        return
    except Exception as e:
        await channel.send(f"❌ `{dd_id}` Opus 調用失敗：{e}")
        return

    ruling_text = raw
    try:
        wrapper = json.loads(raw)
        inner = wrapper.get("result", raw)
        payload = json.loads(inner) if isinstance(inner, str) else inner
        ruling_text = payload.get("content", str(payload))
    except Exception:
        pass

    ts = time.strftime("%Y-%m-%d")
    ruling_path = PROJECT_ROOT / "memory" / "opus_rulings" / f"{ts}_{dd_id}.md"
    ruling_path.parent.mkdir(parents=True, exist_ok=True)
    ruling_path.write_text(ruling_text, encoding="utf-8")

    header = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚖️ **Opus 設計仲裁** — `{dd_id}`\n"
        f"⚠️ **Craig 最終確認後才執行**\n"
        f"裁決檔：`{ruling_path.relative_to(PROJECT_ROOT)}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await channel.send(header)
    for chunk in _split_for_discord(ruling_text):
        await channel.send(chunk)

# ── PM Agent ──────────────────────────────────────────────────────────────────

async def _spawn_pm_headless(topic: str, ticket_id: str, original_message: discord.Message, prior_context: str = ""):
    context_block = f"\n上一則 PM 回應（供參考）：\n{prior_context}\n" if prior_context else ""

    pm_prompt = (
        "[PERSONA: PM] 你是 PM Sonnet，吉寶軒 Antique Pavilion 的專案經理。"
        "使用繁體中文回應（程式碼、檔名、專有名詞保持英文）。\n\n"
        f"Craig 在 #ap-pm 發出以下訊息：\n\n"
        f"訊息（{ticket_id}）：{topic}\n"
        f"{context_block}\n"
        "步驟：\n"
        "1. 讀取 memory/agent_tasks.yaml — 查看目前 Sprint 任務與狀態。\n"
        "2. 讀取 CLAUDE.md — 了解專案架構與原則。\n"
        "3. 用繁體中文直接回覆 Craig，涵蓋：\n"
        "   - 針對 Craig 說的每一點給出明確回應\n"
        "   - 建議行動與負責 Agent（PM / Designer / Dev / Marketing）\n"
        "   - 阻塞項目與需要升級的事項\n"
        "   - 具體下一步（格式：T-XXX → Agent → 行動）\n"
        "只輸出 Discord 訊息本文，不要有其他內容。不要用 # 開頭的標題。\n\n"
        "如果識別到需要 Opus 設計仲裁的項目（高衝突設計決策、品牌方向分歧），"
        "在訊息最末尾加上：\n"
        "OPUS_ESCALATE:\n"
        "- <設計議題標題，20字內>\n"
        "最多 3 項。若無需 Opus 裁決則不要輸出 OPUS_ESCALATE 區塊。"
    )

    cmd = _build_claude_cmd([
        "claude", "-p", pm_prompt,
        "--model", "claude-sonnet-4-6",
        "--allowedTools", "Read,Grep,Glob",
        "--max-turns", "8",
    ])
    log.info("Spawning PM Sonnet for %s", ticket_id)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        raw = stdout.decode("utf-8", errors="replace").strip()
        pm_text = raw if raw else "（PM Sonnet 未產生任何回應）"
    except asyncio.TimeoutError:
        pm_text = f"⚠️ PM Sonnet 逾時（>5 分鐘），票號 `{ticket_id}`。"
    except FileNotFoundError:
        pm_text = "❌ 找不到 `claude` CLI，請確認 Claude Code 已安裝於 WSL2。"
    except Exception as e:
        pm_text = f"❌ PM 啟動錯誤：{e}"

    clean_text, opus_items = _parse_opus_items(pm_text)
    header = f"🤖 **PM Sonnet** — `{ticket_id}`"
    channel = original_message.channel
    try:
        await original_message.reply(header, mention_author=False)
        for chunk in _split_for_discord(clean_text):
            await channel.send(chunk)
        if opus_items:
            view = DesignEscalateView(opus_items, ticket_id, channel)
            await channel.send(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎨 **需要 Opus 設計仲裁** — 點擊項目送審（Craig 確認後才啟動）：",
                view=view
            )
    except Exception as e:
        log.error("Failed to send PM reply: %s", e)

# ── Designer Agent ────────────────────────────────────────────────────────────

async def _spawn_designer_headless(topic: str, ticket_id: str, original_message: discord.Message):
    designer_prompt = (
        "[PERSONA: Designer] 你是吉寶軒的 Designer Agent，專精高奢中國古董藝廊 UI/UX 設計。\n"
        "你的設計標準參考：Sotheby's Asia、Christie's Hong Kong、中國嘉德、保利拍賣、故宮精品。\n\n"
        f"Craig 的設計請求（{ticket_id}）：{topic}\n\n"
        "步驟：\n"
        "1. 讀取 .claude/commands/taste-skill.md — 載入品牌設計規範與反 AI 俗氣規則。\n"
        "2. 讀取 .claude/commands/impeccable-audit.md — 載入設計品質審查框架（5 維度，P0-P3）。\n"
        "3. 讀取 Publish/index.html — 了解當前實作。\n"
        "4. 用繁體中文輸出設計提案，格式如下：\n\n"
        "   **DP-XXX — [提案標題]**\n"
        "   **現況診斷**：[P0/P1/P2/P3 問題清單]\n"
        "   **設計方向**：[符合 Sotheby's 標準的建議，引用品牌 token]\n"
        "   **具體 CSS/HTML 變更**：[代碼片段]\n"
        "   **品牌合規性**：[引用 taste-skill 哪條規則]\n\n"
        "若提案涉及高衝突設計方向（需要拍板），在末尾加上：\n"
        "OPUS_ESCALATE:\n"
        "- <設計仲裁標題，20字內>\n"
        "只輸出提案本文，不要有其他說明。"
    )

    cmd = _build_claude_cmd([
        "claude", "-p", designer_prompt,
        "--model", "claude-sonnet-4-6",
        "--allowedTools", "Read,Grep,Glob",
        "--max-turns", "10",
    ])
    log.info("Spawning Designer Sonnet for %s", ticket_id)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        raw = stdout.decode("utf-8", errors="replace").strip()
        agent_text = raw if raw else "（Designer Agent 未產生回應）"
    except asyncio.TimeoutError:
        agent_text = f"⚠️ Designer Agent 逾時，票號 `{ticket_id}`。"
    except Exception as e:
        agent_text = f"❌ Designer 啟動錯誤：{e}"

    clean_text, opus_items = _parse_opus_items(agent_text)
    header = f"🎨 **Designer Agent** — `{ticket_id}`"
    channel = original_message.channel
    await original_message.reply(header, mention_author=False)
    for chunk in _split_for_discord(clean_text):
        await channel.send(chunk)
    if opus_items:
        view = DesignEscalateView(opus_items, ticket_id, channel)
        await channel.send(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎨 **高衝突設計決策 — 需 Opus 仲裁**（Craig 確認後送審）：",
            view=view
        )

# ── Dev Agent ─────────────────────────────────────────────────────────────────

async def _spawn_dev_headless(topic: str, ticket_id: str, original_message: discord.Message):
    dev_prompt = (
        "[PERSONA: Dev] 你是吉寶軒的 Dev Agent，負責前後端實作與 GAS 腳本維護。\n"
        "技術棧限制：純 HTML/CSS/JS（不引入框架），GAS（Google Apps Script），GitHub Pages。\n\n"
        f"Craig 的開發請求（{ticket_id}）：{topic}\n\n"
        "步驟：\n"
        "1. 讀取 CLAUDE.md — 了解技術限制與欄位結構（Sheets 欄位凍結）。\n"
        "2. 讀取 Publish/index.html — 了解當前前端實作。\n"
        "3. 視需要讀取 memory/Antique_GAS_v9_Discord.md — 了解 GAS 腳本。\n"
        "4. 用繁體中文輸出：\n"
        "   - Bug 診斷 / 功能實作方案\n"
        "   - 具體代碼片段（可直接貼入的 HTML/CSS/JS 或 GAS）\n"
        "   - 跨系統同步注意事項（若涉及 Sheets 欄位，列出需同步的位置）\n"
        "   - 測試步驟\n\n"
        "不要動 Sheets 欄位結構，不要自行決定品項上架。\n"
        "若提案涉及欄位增減（需 Craig 核准），在末尾加上：\n"
        "OPUS_ESCALATE:\n"
        "- <架構決策標題，20字內>\n"
        "只輸出開發建議本文。"
    )

    cmd = _build_claude_cmd([
        "claude", "-p", dev_prompt,
        "--model", "claude-sonnet-4-6",
        "--allowedTools", "Read,Grep,Glob",
        "--max-turns", "10",
    ])
    log.info("Spawning Dev Sonnet for %s", ticket_id)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        raw = stdout.decode("utf-8", errors="replace").strip()
        agent_text = raw if raw else "（Dev Agent 未產生回應）"
    except asyncio.TimeoutError:
        agent_text = f"⚠️ Dev Agent 逾時，票號 `{ticket_id}`。"
    except Exception as e:
        agent_text = f"❌ Dev 啟動錯誤：{e}"

    clean_text, opus_items = _parse_opus_items(agent_text)
    header = f"💻 **Dev Agent** — `{ticket_id}`"
    channel = original_message.channel
    await original_message.reply(header, mention_author=False)
    for chunk in _split_for_discord(clean_text):
        await channel.send(chunk)
    if opus_items:
        view = DesignEscalateView(opus_items, ticket_id, channel)
        await channel.send("⚠️ **架構決策需要確認** — 點擊送審：", view=view)

# ── Marketing Agent ───────────────────────────────────────────────────────────

async def _spawn_marketing_headless(topic: str, ticket_id: str, original_message: discord.Message):
    marketing_prompt = (
        "[PERSONA: Marketing] 你是吉寶軒的 Marketing Agent，負責內容行銷與社群策略。\n"
        "品牌聲音：典雅、含蓄、第三人稱機構語氣（如拍賣圖錄）。無驚嘆號，無表情符號。\n\n"
        f"Craig 的行銷請求（{ticket_id}）：{topic}\n\n"
        "步驟：\n"
        "1. 讀取 .claude/commands/copywriting.md — 載入文案規則。\n"
        "2. 讀取 .claude/commands/social-content.md — 載入社群內容策略。\n"
        "3. 讀取 .claude/commands/marketing-psychology.md — 載入買家心理框架。\n"
        "4. 用繁體中文輸出：\n"
        "   - 文案方案 / 內容日曆\n"
        "   - 平台差異化建議（Instagram / LINE / Facebook）\n"
        "   - 骨董市場社群經營建議\n\n"
        "只輸出行銷建議本文。"
    )

    cmd = _build_claude_cmd([
        "claude", "-p", marketing_prompt,
        "--model", "claude-sonnet-4-6",
        "--allowedTools", "Read,Grep,Glob",
        "--max-turns", "8",
    ])
    log.info("Spawning Marketing Sonnet for %s", ticket_id)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        raw = stdout.decode("utf-8", errors="replace").strip()
        agent_text = raw if raw else "（Marketing Agent 未產生回應）"
    except asyncio.TimeoutError:
        agent_text = f"⚠️ Marketing Agent 逾時，票號 `{ticket_id}`。"
    except Exception as e:
        agent_text = f"❌ Marketing 啟動錯誤：{e}"

    header = f"📣 **Marketing Agent** — `{ticket_id}`"
    channel = original_message.channel
    await original_message.reply(header, mention_author=False)
    for chunk in _split_for_discord(agent_text):
        await channel.send(chunk)

# ── 自動執行引擎 ──────────────────────────────────────────────────────────────
# 批准後根據任務類別自動路由：
#   視覺設計 / 互動體驗 → 直接修改 index.html + git push
#   功能 / 其他         → 讀 GAS 腳本，輸出代碼方案供 Craig 手動部署

FRONTEND_CATEGORIES = {"視覺設計", "互動體驗"}


async def _spawn_auto_execute_task(proposal: dict, poll_id: str, channel: discord.TextChannel):
    """
    前端類任務自動執行：
    Claude Code CLI 修改 index.html → 同步 Publish/index.html → git push
    Craig 不在線時全程自動完成並回報結果。
    """
    title   = proposal.get("title", "未命名任務")
    problem = proposal.get("problem", "")
    solution = proposal.get("solution", "")
    priority = proposal.get("priority", "P2")
    ticket  = f"AUTO-{poll_id}-{priority}"

    await channel.send(
        f"⚙️ **自動執行中** `{ticket}`\n"
        f"**{title}**\n"
        f"Dev Agent 正在讀取代碼並實作，約 2–3 分鐘..."
    )

    execution_prompt = (
        "[PERSONA: Autonomous Dev Agent]\n"
        "你是吉寶軒自動化開發代理人，請直接修改檔案（不是提建議），然後部署到 GitHub Pages。\n\n"
        f"任務票號：{ticket}\n"
        f"任務標題：{title}\n"
        f"問題描述：{problem}\n"
        f"解決方向：{solution}\n\n"
        "【執行步驟 — 必須依序完成】\n"
        "1. 讀取 index.html 了解目前代碼結構\n"
        "2. 定位問題所在的 CSS / HTML 區塊\n"
        "3. 用 Edit 工具修改 index.html\n"
        "4. 將相同修改同步套用到 Publish/index.html\n"
        f"5. 執行 git add Publish/index.html index.html\n"
        f"6. 執行 git commit -m 'Auto[{ticket}]: {title}'\n"
        "7. 執行 git push（若失敗請記錄錯誤訊息，不要重試，繼續下一步）\n"
        "8. 輸出完成報告：\n"
        "   - 修改了什麼 CSS rule、在哪幾行\n"
        "   - git push 結果（成功 or 失敗原因）\n"
        "   - 若 git 未初始化，提示：需在 WSL2 執行 STARTUP.md 的 Git 設定步驟\n\n"
        "【硬性約束 — 違反則任務失敗】\n"
        "- 只修改 CSS 和 HTML 結構，不動 JavaScript 業務邏輯\n"
        "- 維持現有設計系統變數（--gold, --ink, --paper, --seal-red）\n"
        "- 不引入任何外部框架或 npm 套件\n"
        "- 保留所有 ARIA 屬性與無障礙設計\n"
        "- 不修改 Google Sheets 欄位結構（欄位已凍結）\n"
        "- 輸出以「✅ 自動執行完成」開頭的繁體中文摘要\n"
    )

    cmd = _build_claude_cmd([
        "claude", "-p", execution_prompt,
        "--model", "claude-sonnet-4-6",
        "--allowedTools", "Read,Edit,Write,Glob,Grep,Bash",
        "--max-turns", "20",
    ])

    log.info("[AutoDev] 啟動前端自動執行 %s", ticket)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
        result = stdout.decode("utf-8", errors="replace").strip()
        result = result if result else "（Dev Agent 未產生回應）"
        log.info("[AutoDev] ✅ 執行完成 %s", ticket)
    except asyncio.TimeoutError:
        result = f"⚠️ 自動執行逾時（10 分鐘），任務 `{ticket}` 需手動處理。"
        log.error("[AutoDev] 逾時 %s", ticket)
    except Exception as e:
        result = f"❌ 自動執行失敗：{e}"
        log.error("[AutoDev] 錯誤 %s: %s", ticket, e)

    await channel.send(f"📋 **執行報告** — `{ticket}`")
    for chunk in _split_for_discord(result):
        await channel.send(chunk)


async def _spawn_auto_gas_task(proposal: dict, poll_id: str, channel: discord.TextChannel):
    """
    GAS / 功能類任務：
    Claude Code CLI 讀取現有 GAS 腳本，輸出具體修改代碼，
    發送到 #ap-web-dev 供 Craig 手動貼入 Google Apps Script 重新部署。
    """
    title    = proposal.get("title", "未命名任務")
    problem  = proposal.get("problem", "")
    solution = proposal.get("solution", "")
    priority = proposal.get("priority", "P2")
    ticket   = f"GAS-{poll_id}-{priority}"

    await channel.send(
        f"⚙️ **GAS 代碼生成中** `{ticket}`\n"
        f"**{title}**\n"
        f"Dev Agent 正在分析 GAS 腳本，約 1–2 分鐘..."
    )

    gas_prompt = (
        "[PERSONA: GAS Dev Agent]\n"
        "你是吉寶軒 Google Apps Script 開發代理人。\n\n"
        f"任務票號：{ticket}\n"
        f"任務標題：{title}\n"
        f"問題描述：{problem}\n"
        f"解決方向：{solution}\n\n"
        "【執行步驟】\n"
        "1. 讀取 memory/Antique_GAS_v9_Discord.md — 了解當前 GAS 腳本完整內容\n"
        "2. 讀取 CLAUDE.md — 確認欄位凍結規範與系統約束\n"
        "3. 輸出具體的 GAS 代碼修改（可直接貼入 Google Apps Script 的完整函式）\n"
        "4. 說明修改位置：哪個函式、第幾行、修改了什麼\n"
        "5. 若涉及前端篩選器同步，同時說明 Publish/index.html 需對應調整的部分\n"
        "6. 提醒 Craig 修改後需在 Google Apps Script 重新部署 Web App\n\n"
        "【約束】\n"
        "- 不可新增 Sheets 欄位（除非有 Craig 明確批准的 DD-XXX 記錄）\n"
        "- 代碼必須與現有 v9.0 架構相容\n"
        "- 輸出以「📋 GAS 修改方案」開頭的繁體中文說明\n"
    )

    cmd = _build_claude_cmd([
        "claude", "-p", gas_prompt,
        "--model", "claude-sonnet-4-6",
        "--allowedTools", "Read,Grep,Glob",
        "--max-turns", "8",
    ])

    log.info("[AutoGAS] 啟動 GAS 代碼生成 %s", ticket)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        result = stdout.decode("utf-8", errors="replace").strip()
        result = result if result else "（GAS Dev Agent 未產生回應）"
        log.info("[AutoGAS] ✅ 代碼生成完成 %s", ticket)
    except asyncio.TimeoutError:
        result = f"⚠️ GAS 代碼生成逾時（5 分鐘），任務 `{ticket}` 需手動處理。"
        log.error("[AutoGAS] 逾時 %s", ticket)
    except Exception as e:
        result = f"❌ GAS 代碼生成失敗：{e}"
        log.error("[AutoGAS] 錯誤 %s: %s", ticket, e)

    await channel.send(
        f"📋 **GAS 實作方案** — `{ticket}`\n"
        f"⚠️ 以下代碼請手動貼入 Google Apps Script 並重新部署 Web App"
    )
    for chunk in _split_for_discord(result):
        await channel.send(chunk)


# ── Bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
AGENDA_PREFIX = "!agenda"

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

scheduler = AsyncIOScheduler(timezone=TAIPEI_TZ)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.CommandNotFound):
        return
    log.error("Command error: %s", error)


@bot.event
async def on_ready():
    log.info("ORG Bot ready as %s (ID: %s)", bot.user, bot.user.id)
    log.info("   #ap-feedback : %s", CHANNEL_FEEDBACK)
    try:
        synced = await tree.sync()
        log.info("Synced %d slash commands.", len(synced))
    except Exception as e:
        log.error("Failed to sync slash commands: %s", e)

    # 啟動 Feedback PM 排程
    if not scheduler.running:
        scheduler.add_job(
            lambda: asyncio.create_task(run_feedback_poll()),
            trigger="cron", hour=POLL_HOUR_1, minute=0,
            id="poll_morning", replace_existing=True
        )
        scheduler.add_job(
            lambda: asyncio.create_task(run_feedback_poll()),
            trigger="cron", hour=POLL_HOUR_2, minute=0,
            id="poll_evening", replace_existing=True
        )
        scheduler.add_job(
            lambda: asyncio.create_task(check_expired_proposals()),
            trigger="cron", hour=0, minute=30,
            id="expiry_check", replace_existing=True
        )
        scheduler.start()
        log.info("排程啟動：Poll %d:00 / %d:00，Expiry 00:30（台北時間）",
                 POLL_HOUR_1, POLL_HOUR_2)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id = message.channel.id

    # ── #ap-feedback：開放白名單用戶投遞意見，排程 Poll 時讀取 ─────────────
    # 必須在 Craig-only 閘門之前處理，否則夥伴訊息會被擋掉
    if channel_id == CHANNEL_FEEDBACK:
        if str(message.author.id) in ALLOWED_USER_IDS:
            log.info("[Feedback] 📝 收到新意見 from %s (#%s): %.80s",
                     message.author.display_name,
                     message.channel.name,
                     message.content)
            await message.add_reaction("📝")
        await bot.process_commands(message)
        return

    # ── ORG 頻道：Craig 專屬 ───────────────────────────────────────────────
    craig_id = _env("DISCORD_CRAIG_USER_ID")
    if craig_id and str(message.author.id) != craig_id:
        return

    content = message.content.strip()
    if not content:
        return

    ticket_id = f"AG-{time.strftime('%Y%m%d-%H%M%S')}"

    # 處理 Reply（對話延續，適用所有頻道）
    if message.reference:
        ref = message.reference.resolved
        if ref is None:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
            except Exception:
                ref = None
        if isinstance(ref, discord.Message) and ref.author.id == bot.user.id:
            ticket_id = f"AG-{time.strftime('%Y%m%d-%H%M%S')}-cont"
            prior = ref.content[:800] if ref.content else ""
            await message.add_reaction("⚙️")
            if channel_id == CHANNEL_PM:
                asyncio.create_task(_spawn_pm_headless(content, ticket_id, message, prior_context=prior))
            elif channel_id == CHANNEL_DESIGN:
                asyncio.create_task(_spawn_designer_headless(content, ticket_id, message))
            elif channel_id == CHANNEL_DEV:
                asyncio.create_task(_spawn_dev_headless(content, ticket_id, message))
            elif channel_id == CHANNEL_MARKETING:
                asyncio.create_task(_spawn_marketing_headless(content, ticket_id, message))
            await bot.process_commands(message)
            return

    # #ap-pm：!agenda 觸發 PM Agent
    if channel_id == CHANNEL_PM and content.lower().startswith(AGENDA_PREFIX):
        topic = content[len(AGENDA_PREFIX):].strip()
        if not topic:
            await message.reply("使用方式：`!agenda <議題>`")
            return
        await message.add_reaction("⚙️")
        _log_inbox(topic)
        await message.reply(f"📋 `{ticket_id}` — PM Sonnet 收到，分析中...", mention_author=False)
        asyncio.create_task(_spawn_pm_headless(topic, ticket_id, message))

    # #ap-web-design：任何訊息 → Designer Agent
    elif channel_id == CHANNEL_DESIGN:
        await message.add_reaction("🎨")
        await message.reply(f"🎨 `{ticket_id}` — Designer Agent 收到，載入品牌規範中...", mention_author=False)
        asyncio.create_task(_spawn_designer_headless(content, ticket_id, message))

    # #ap-web-dev：任何訊息 → Dev Agent
    elif channel_id == CHANNEL_DEV:
        await message.add_reaction("💻")
        await message.reply(f"💻 `{ticket_id}` — Dev Agent 收到，分析代碼中...", mention_author=False)
        asyncio.create_task(_spawn_dev_headless(content, ticket_id, message))

    # #ap-marketing：任何訊息 → Marketing Agent
    elif channel_id == CHANNEL_MARKETING:
        await message.add_reaction("📣")
        await message.reply(f"📣 `{ticket_id}` — Marketing Agent 收到，載入文案框架中...", mention_author=False)
        asyncio.create_task(_spawn_marketing_headless(content, ticket_id, message))

    await bot.process_commands(message)


def _log_inbox(topic: str):
    inbox_file = PROJECT_ROOT / "memory" / "agent_inbox.md"
    ts_str = time.strftime("%Y-%m-%d %H:%M")
    try:
        with open(inbox_file, "a", encoding="utf-8") as f:
            f.write(f"\n[{ts_str}] {topic}\n")
    except Exception:
        pass

# ── Slash Commands ────────────────────────────────────────────────────────────

@tree.command(name="veto", description="緊急凍結：停止所有 in-flight agent 調用。")
@app_commands.describe(reason="凍結原因")
async def veto_cmd(interaction: discord.Interaction, reason: str):
    craig_id = _env("DISCORD_CRAIG_USER_ID")
    if craig_id and str(interaction.user.id) != craig_id:
        await interaction.response.send_message("只有 Craig 可以發出 VETO。", ephemeral=True)
        return
    veto_file = PROJECT_ROOT / "memory" / "VETO_ACTIVE.json"
    veto_file.write_text(json.dumps({
        "active": True, "reason": reason,
        "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    await interaction.response.send_message(f"🛑 **VETO ACTIVE**\n原因：_{reason}_")


@tree.command(name="sprint", description="查看當前 Sprint 任務狀態。")
async def sprint_cmd(interaction: discord.Interaction):
    tasks_file = PROJECT_ROOT / "memory" / "agent_tasks.yaml"
    if not tasks_file.exists():
        await interaction.response.send_message("❌ `memory/agent_tasks.yaml` 不存在。", ephemeral=True)
        return
    content = tasks_file.read_text(encoding="utf-8")[:1800]
    await interaction.response.send_message(f"📋 **Sprint 狀態**\n```yaml\n{content}\n```")


@tree.command(name="poll-now", description="立即觸發 #ap-feedback 反饋彙整（Craig 專用）")
async def poll_now_cmd(interaction: discord.Interaction):
    if str(interaction.user.id) not in ALLOWED_USER_IDS:
        await interaction.response.send_message("只有授權用戶可以執行。", ephemeral=True)
        return
    await interaction.response.send_message("⚙️ 手動觸發 Feedback Poll，請稍候...", ephemeral=True)
    asyncio.create_task(run_feedback_poll())


@tree.command(name="usage-status", description="查看 Claude PM 本月 CLI 呼叫次數")
async def usage_status_cmd(interaction: discord.Interaction):
    if str(interaction.user.id) not in ALLOWED_USER_IDS:
        await interaction.response.send_message("只有授權用戶可以查看。", ephemeral=True)
        return
    state  = load_state()
    calls  = state.get("monthly_calls", 0)
    month  = state.get("month_key", "—")
    pct    = calls / MONTHLY_CALL_LIMIT * 100
    bar    = "🟩" if pct < 50 else ("🟨" if pct < 80 else "🟥")
    await interaction.response.send_message(
        f"📊 **Claude PM 本月使用量**（MAX 訂閱，無額外計費）\n"
        f"{bar} {month}：{calls} / {MONTHLY_CALL_LIMIT} 次 ({pct:.0f}%)\n"
        f"_每次 Poll 消耗 1 次，每月最多 {MONTHLY_CALL_LIMIT} 次_",
        ephemeral=True
    )

# ── 入口 ──────────────────────────────────────────────────────────────────────

def run_bot():
    token = _env("DISCORD_ORG_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_ORG_BOT_TOKEN not set in .env.antique")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    run_bot()
