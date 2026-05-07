"""
🏺 吉寶軒 — 骨董識別鑑定助理 Bot  v2.2
================================================================
功能：#antique-analysis 頻道骨董圖片鑑定

流程：
  用戶上傳圖片 → Gateway on_message
  → 下載圖片 → GAS doPost → Gemini 鑑定 → Embed 報告

架構決策（2026-04-24）：
  - Gateway 模式取代舊版 REST 輪詢（即時觸發，無 60 秒延遲）
  - SSL patch 在 module level（Thor 風格，先於 discord/aiohttp import）
  - Feedback PM 功能已移入 scripts/ap_org_bot.py（ORG Bot 職責）

版本：v2.2.0 (2026-04-24)
"""

import asyncio
import base64
import logging
import os
import ssl as _ssl
from datetime import datetime, timezone
from pathlib import Path

import pytz

# ── Env loader（讀取 .env.antique，敏感資料不入 Git）────────────────────────
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

_PROJECT_ROOT = Path(__file__).resolve().parent

# ── Phase A: Notion writer (opt-in via NOTION_API_KEY) ──
try:
    import sys as _sys_n
    _sys_n.path.insert(0, str(_PROJECT_ROOT / "scripts"))
    from notion_writer import (
        is_enabled as notion_enabled,
        create_authentication_log,
    )
except Exception as _e:
    import logging as _lg
    _lg.getLogger("ap_discord_bot").warning("[notion] notion_writer not loaded: %s", _e)
    def notion_enabled(): return False
    def create_authentication_log(*a, **k): return None
_ENV = _load_env(_PROJECT_ROOT / ".env.antique")

# ================================================================
# ⚡ SSL PATCH — module level, before any discord/aiohttp import
#    企業 Windows Proxy 注入自簽憑證，統一 bypass 所有 TLS 驗證
#    Reference: Thor discord_bot_v2.py
# ================================================================
_orig_ssl_ctx = _ssl.create_default_context
def _no_verify_ssl_ctx(*args, **kwargs):
    ctx = _orig_ssl_ctx(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode    = _ssl.CERT_NONE
    return ctx
_ssl.create_default_context = _no_verify_ssl_ctx

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

# ================================================================
# ⚙️  設定
# ================================================================
BOT_TOKEN = _ENV.get("DISCORD_BOT_TOKEN", os.getenv("DISCORD_BOT_TOKEN", ""))

GAS_DOPOST_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbz6wId1wRbY48o7xH2X4T0e7UFlppakZvBYmJn4KybA6uGgzk4CZs8YXQSTZoj2Suhiew/exec"
)

ANTIQUE_CHANNEL_ID = 1495279823009087551   # #antique-analysis
PROCESSING_REACTION = "🏺"               # reaction 標記：已收到，catch-up 補跑依此判斷

# 白名單：可上傳圖片的 Discord User ID
ALLOWED_USER_IDS = {
    "566565645483769863",       # Craig
    "1495302135112401067",      # 協作夥伴
}

TAIPEI_TZ = pytz.timezone("Asia/Taipei")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("ap_antique_bot")

# ================================================================
# Discord Bot 初始化（Gateway 模式）
# ================================================================
intents = discord.Intents.default()
intents.message_content = True   # 必須：讀取訊息文字內容

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ================================================================
# 事件處理
# ================================================================
@bot.event
async def on_ready():
    log.info("🏺 鑑定助理 Bot 上線：%s (ID: %s)", bot.user, bot.user.id)
    log.info("   #antique-analysis : %s", ANTIQUE_CHANNEL_ID)
    try:
        synced = await tree.sync()
        log.info("Slash commands 同步：%d 個", len(synced))
    except Exception as e:
        log.error("Slash command 同步失敗: %s", e)
    # 補跑離線期間未處理訊息
    await catch_up_missed_messages()


async def catch_up_missed_messages():
    """掃描 #antique-analysis 最近 100 則，補跑沒有 🏺 reaction 的白名單圖片訊息"""
    channel = bot.get_channel(ANTIQUE_CHANNEL_ID)
    if not channel:
        log.warning("[CatchUp] 找不到頻道 %s", ANTIQUE_CHANNEL_ID)
        return
    log.info("[CatchUp] 掃描離線期間未處理訊息（最近 100 則）...")
    caught = 0
    async for message in channel.history(limit=100):
        if message.author.bot:
            continue
        if str(message.author.id) not in ALLOWED_USER_IDS:
            continue
        images = [
            a for a in message.attachments
            if a.content_type and a.content_type.startswith("image/")
        ]
        if not images:
            continue
        # 已有 🏺 reaction（bot 自己加的）→ 已處理，略過
        already = any(str(r.emoji) == PROCESSING_REACTION and r.me for r in message.reactions)
        if already:
            continue
        log.info("[CatchUp] 補跑 msgId=%s author=%s", message.id, message.author.display_name)
        await handle_antique_message(message)
        caught += 1
        await asyncio.sleep(2)   # rate-limit buffer：避免短時間大量呼叫 GAS
    log.info("[CatchUp] 完成，共補跑 %d 則", caught)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.id == ANTIQUE_CHANNEL_ID:
        await handle_antique_message(message)
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    log.error("指令錯誤: %s", error)


# ================================================================
# 鑑定處理
# ================================================================
async def handle_antique_message(message: discord.Message):
    """處理 #antique-analysis 頻道訊息"""
    if str(message.author.id) not in ALLOWED_USER_IDS:
        log.info("[Antique] 非白名單用戶 %s，略過", message.author.id)
        return

    images = [
        a for a in message.attachments
        if a.content_type and a.content_type.startswith("image/")
    ]

    if not images:
        if message.content.strip().lower() == "ping":
            await message.reply("通訊正常，系統待命中。🏺")
        return

    # 先加 🏺 reaction 標記「已收到」，catch-up 補跑邏輯依此判斷是否處理過
    try:
        await message.add_reaction(PROCESSING_REACTION)
    except discord.HTTPException as e:
        log.warning("[Antique] 無法加 reaction: %s", e)

    await message.reply("已收到您的雅器圖片，掌櫃正在調閱典籍鑑定中，請稍候...")
    asyncio.create_task(_process_antique_image(message, images[0]))


async def _process_antique_image(message: discord.Message, attachment: discord.Attachment):
    """下載圖片 → 呼叫 GAS → 發送 Embed（背景任務）"""
    try:
        # 下載圖片（ssl=False：module-level patch 已處理 TLS）
        async with aiohttp.ClientSession() as session:
            async with session.get(
                attachment.url, ssl=False,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    await message.reply(f"圖片下載失敗（HTTP {resp.status}），請重試。")
                    return
                img_data = await resp.read()

        img_b64   = base64.b64encode(img_data).decode("utf-8")
        mime_type = attachment.content_type or "image/jpeg"

        gas_payload = {
            "imageBase64": img_b64,
            "mimeType":    mime_type,
            "caption":     message.content or "無描述",
            "messageId":   str(message.id),
            "channelId":   str(message.channel.id),
            "userId":      str(message.author.id),
            "userName":    message.author.display_name
        }

        log.info("[Antique] 呼叫 GAS 鑑定中... msgId=%s", message.id)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                GAS_DOPOST_URL, json=gas_payload, ssl=False,
                timeout=aiohttp.ClientTimeout(total=180)
            ) as resp:
                if resp.status != 200:
                    await message.reply(f"GAS 處理失敗（HTTP {resp.status}）")
                    return
                result = await resp.json(content_type=None)

        analysis = result.get("analysis", {})
        file_url  = result.get("fileUrl", "")

        if not result.get("success"):
            err_msg = result.get('error', '未知錯誤')
            await message.reply(
                f"**鑑定失敗**\n錯誤：{err_msg}"
            )
            # ── Phase A: 寫到 Authentication Log (opt-in) ──
            if notion_enabled():
                try:
                    create_authentication_log(
                        title=f"[失敗] msgId={message.id}",
                        user=message.author.display_name,
                        gemini_judgment=f"鑑定失敗：{err_msg}",
                        curator_status="退回",
                        notes=f"錯誤：{str(err_msg)[:500]}",
                    )
                except Exception as _e:
                    log.warning("[notion] auth log failed: %s", _e)

        elif not analysis.get("isValid"):
            reject_reason = analysis.get('rejectionReason', '圖片不符合鑑定條件')
            await message.reply(
                f"**鑑定退回**\n\n"
                f"{reject_reason}"
                f"\n\n圖片已存檔：{file_url}"
            )
            # ── Phase A: 寫到 Authentication Log (opt-in) ──
            if notion_enabled():
                try:
                    create_authentication_log(
                        title=f"[退回] msgId={message.id}",
                        user=message.author.display_name,
                        gemini_judgment=f"退回：{reject_reason}",
                        curator_status="退回",
                        notes=f"圖片：{file_url}",
                    )
                except Exception as _e:
                    log.warning("[notion] auth log failed: %s", _e)

        else:
            embed = discord.Embed(
                title       = f"【專屬鑑定報告】{analysis.get('itemName', '器物')}",
                description = analysis.get("story", ""),
                color       = 0xB8960C,
                url         = file_url,
                timestamp   = datetime.now(timezone.utc)
            )
            embed.add_field(
                name="分類", value=analysis.get("category", "不詳"), inline=True
            )
            embed.add_field(
                name="斷代預估", value=analysis.get("era", "不詳"), inline=True
            )
            embed.add_field(
                name="特徵解析", value=analysis.get("features", "不詳"), inline=False
            )
            embed.add_field(
                name="拍賣行參考",
                value=(
                    f"{analysis.get('refItem', '不詳')} "
                    f"(約 {analysis.get('refPrice', '不詳')})"
                ),
                inline=False
            )
            embed.add_field(
                name="展示建議",
                value=analysis.get("displayRecommendation", "不詳"),
                inline=False
            )
            embed.set_footer(
                text=f"雲端歸檔完成 | {datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d %H:%M')}"
            )
            await message.reply(embed=embed)
            log.info("[Antique] ✅ 鑑定完成：%s", analysis.get("itemName", "未知"))

            # ── Phase A: 寫到 Authentication Log (opt-in) ──
            if notion_enabled():
                try:
                    create_authentication_log(
                        title=analysis.get("itemName", "未命名器物"),
                        user=message.author.display_name,
                        gemini_judgment=(
                            f"分類：{analysis.get('category', '不詳')} | "
                            f"斷代：{analysis.get('era', '不詳')}\n"
                            f"特徵：{analysis.get('features', '不詳')[:800]}\n"
                            f"故事：{analysis.get('story', '不詳')[:800]}"
                        ),
                        curator_status="未審",
                        notes=(
                            f"拍賣參考：{analysis.get('refItem', '不詳')} "
                            f"(約 {analysis.get('refPrice', '不詳')})\n"
                            f"圖片：{file_url}\n"
                            f"msgId={message.id}"
                        ),
                    )
                except Exception as _e:
                    log.warning("[notion] auth log failed: %s", _e)

    except Exception as err:
        await message.reply(f"**鑑定失敗**\n{str(err)[:300]}")
        log.error("[Antique] 錯誤: %s", err, exc_info=True)


# ================================================================
# 入口
# ================================================================
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN 不可為空！")
    log.info("🏺 吉寶軒 鑑定助理 Bot v2.2 啟動中...")
    log.info("   按 Ctrl+C 停止")
    bot.run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
