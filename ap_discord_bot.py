"""
🏺 吉寶軒 — 骨董影像編目 Intake Bridge  v3.0
================================================================
功能：#antique-analysis 頻道骨董圖片鑑定

流程：
  用戶同訊息上傳 1–8 張圖片 → Gateway on_message
  → 本地下載與壓縮 → 安全 GAS doPost → Gemini 編目 → Embed 報告

架構決策（2026-04-24）：
  - Gateway 模式取代舊版 REST 輪詢（即時觸發，無 60 秒延遲）
  - 企業 SSL bypass 改為 AP_ENTERPRISE_SSL_BYPASS 明確啟用
  - Feedback PM 功能已移入 scripts/ap_org_bot.py（ORG Bot 職責）

CHANGE GAS-LOCAL-BRIDGE: Discord/Cloudflare 40333 後恢復本地 Gateway I/O；
GAS 仍是 Gemini、Drive、Catalog、AP_MEDIA 的唯一寫入權威。

版本：v3.0.0 (2026-08-31)
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytz

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from ap_intake_bridge import (  # noqa: E402
    ALLOWED_SOURCE_MIME_TYPES,
    MAX_IMAGES_PER_ARTIFACT,
    MAX_SOURCE_IMAGE_BYTES,
    BridgeInputError,
    build_ingest_payload,
    compress_image_bytes,
    per_image_budget,
    validate_bridge_config,
)
from ap_org_bot.infra.env import env, env_bool  # noqa: E402
from ap_org_bot.infra.ssl_patch import apply_enterprise_ssl_bypass  # noqa: E402

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
import aiohttp
import discord
from discord.ext import commands

# ================================================================
# ⚙️  設定
# ================================================================
BOT_TOKEN = env("DISCORD_BOT_TOKEN")
GAS_DOPOST_URL = env("AP_GAS_DOPOST_URL")
AP_INGEST_SECRET = env("AP_INGEST_SECRET")
ENTERPRISE_SSL_BYPASS = env_bool("AP_ENTERPRISE_SSL_BYPASS", False)

ANTIQUE_CHANNEL_ID = 1495279823009087551   # #antique-analysis
PROCESSING_REACTION = "⏳"
COMPLETED_REACTION = "🏺"
MANUAL_REVIEW_REACTION = "⚠️"

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
_active_message_ids: set[int] = set()
_intake_semaphore = asyncio.Semaphore(1)

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
    """補跑沒有完成或人工停手標記的白名單圖片訊息。"""
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
            if str(a.content_type or "").lower().startswith("image/")
        ]
        if not images:
            continue
        reactions = {str(reaction.emoji) for reaction in message.reactions if reaction.me}
        if COMPLETED_REACTION in reactions or MANUAL_REVIEW_REACTION in reactions:
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

    image_attachments = [
        a for a in message.attachments
        if str(a.content_type or "").lower().startswith("image/")
    ]

    if not image_attachments:
        if message.content.strip().lower() == "ping":
            await message.reply("通訊正常，系統待命中。🏺")
        return

    unsupported = [
        attachment
        for attachment in image_attachments
        if str(attachment.content_type or "").lower() not in ALLOWED_SOURCE_MIME_TYPES
    ]
    if unsupported:
        await message.reply(
            "目前只接受 JPEG、PNG、WebP；本則含不支援的影像格式，整則未送出。"
            "請先轉成 JPG 後再上傳。"
        )
        await _set_terminal_reaction(message, MANUAL_REVIEW_REACTION)
        return
    images = image_attachments

    if len(images) > MAX_IMAGES_PER_ARTIFACT:
        await message.reply(
            f"同一件藏品最多 {MAX_IMAGES_PER_ARTIFACT} 張；本則共有 {len(images)} 張。"
            "請精選正面、背面／側面、底部、款識與局部後重新上傳。"
        )
        await _set_terminal_reaction(message, MANUAL_REVIEW_REACTION)
        return

    if message.id in _active_message_ids:
        log.info("[Antique] msgId=%s 已在本機處理中，略過重複事件", message.id)
        return
    completed = any(
        str(reaction.emoji) == COMPLETED_REACTION and reaction.me
        for reaction in message.reactions
    )
    if completed:
        log.info("[Antique] msgId=%s 已完成，略過", message.id)
        return

    _active_message_ids.add(message.id)
    try:
        await message.add_reaction(PROCESSING_REACTION)
    except discord.HTTPException as e:
        log.warning("[Antique] 無法加 reaction: %s", e)

    await message.reply(
        f"已收到同一件藏品的 {len(images)} 張圖片，正在本地壓縮並送交 GAS 進行影像編目，請稍候..."
    )
    asyncio.create_task(_process_antique_images(message, images))


async def _download_and_prepare_images(attachments: list[discord.Attachment]):
    target_bytes = per_image_budget(len(attachments))
    prepared = []
    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for index, attachment in enumerate(attachments, start=1):
            if attachment.size and attachment.size > MAX_SOURCE_IMAGE_BYTES:
                raise BridgeInputError(
                    f"第 {index} 張原圖 {attachment.size} bytes，超過 30 MiB 本地安全上限"
                )
            async with session.get(attachment.url) as response:
                if response.status != 200:
                    raise RuntimeError(f"第 {index} 張圖片下載失敗（HTTP {response.status}）")
                chunks = []
                source_bytes = 0
                async for chunk in response.content.iter_chunked(256 * 1024):
                    source_bytes += len(chunk)
                    if source_bytes > MAX_SOURCE_IMAGE_BYTES:
                        raise BridgeInputError(
                            f"第 {index} 張實際下載量超過 30 MiB 本地安全上限"
                        )
                    chunks.append(chunk)
                source = b"".join(chunks)
            prepared.append(
                await asyncio.to_thread(
                    compress_image_bytes,
                    source,
                    attachment_id=str(attachment.id),
                    filename=attachment.filename or f"antique_{index}.jpg",
                    index=index,
                    target_bytes=target_bytes,
                )
            )
    return prepared


async def _post_to_gas(payload: dict[str, object]) -> dict[str, object]:
    timeout = aiohttp.ClientTimeout(total=210)
    last_error: Exception | None = None
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, 4):
            try:
                async with session.post(GAS_DOPOST_URL, json=payload) as response:
                    body = await response.text()
                    if response.status != 200:
                        if response.status == 429 or response.status >= 500:
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=response.status,
                                message="GAS transient HTTP",
                            )
                        raise RuntimeError(f"GAS HTTP {response.status}；拒絕自動重送")
                    if body.lstrip().lower().startswith("<!doctype"):
                        raise RuntimeError(
                            "GAS Web App 未開放匿名 /exec 存取，回傳 HTML；拒絕自動重送"
                        )
                    try:
                        result = json.loads(body)
                    except ValueError as exc:
                        raise RuntimeError("GAS 回傳非 JSON；拒絕自動重送") from exc
                    if not isinstance(result, dict):
                        raise RuntimeError("GAS JSON 不是 object；拒絕自動重送")
                    if (
                        result.get("success") is False
                        and result.get("code") == "INGEST_IN_PROGRESS"
                        and result.get("retrySafe") is True
                    ):
                        last_error = RuntimeError("相同 messageId 仍在 GAS 處理中")
                        if attempt < 3:
                            log.warning(
                                "[Antique] GAS 尚在處理 msgId=%s；%d 秒後重查既有結果",
                                payload.get("messageId"),
                                5 * attempt,
                            )
                            await asyncio.sleep(5 * attempt)
                            continue
                    return result
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt >= 3:
                    break
                log.warning(
                    "[Antique] GAS transport 第 %d 次暫時失敗，將以同 messageId 重試：%s",
                    attempt,
                    exc,
                )
                await asyncio.sleep(2 * attempt)
    raise RuntimeError(f"GAS transport 失敗：{last_error}")


async def _set_terminal_reaction(message: discord.Message, emoji: str) -> None:
    try:
        await message.add_reaction(emoji)
        if bot.user:
            await message.remove_reaction(PROCESSING_REACTION, bot.user)
    except discord.HTTPException as exc:
        log.warning("[Antique] reaction 更新失敗 msgId=%s: %s", message.id, exc)


async def _send_bridge_result(message: discord.Message, result: dict[str, object]) -> None:
    analysis = result.get("analysis") if isinstance(result.get("analysis"), dict) else {}
    file_url = str(result.get("fileUrl") or "")
    image_count = int(result.get("imageCount") or 0)
    if not analysis.get("isValid"):
        reject_reason = analysis.get("rejectionReason", "圖片不足以進入編目")
        await message.reply(
            f"**影像資料待補**\n\n{reject_reason}\n\n"
            f"已保留 {image_count or len(message.attachments)} 張原圖，尚未公開。"
        )
        return

    embed = discord.Embed(
        title=f"【器物影像編目初稿】{analysis.get('itemName', '器物')}",
        description=str(analysis.get("story") or "")[:4096],
        color=0xB8960C,
        url=file_url or None,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="分類", value=analysis.get("category", "不詳"), inline=True)
    embed.add_field(name="年代初判（待覆核）", value=analysis.get("era", "不詳"), inline=True)
    embed.add_field(name="影像觀察", value=str(analysis.get("features") or "不詳")[:1024], inline=False)
    if analysis.get("refItem") or analysis.get("refPrice"):
        reference = "｜".join(str(value) for value in (analysis.get("refItem"), analysis.get("refPrice")) if value)
        embed.add_field(name="已提供參考資料", value=reference[:1024], inline=False)
    embed.add_field(
        name="陳設建議",
        value=str(analysis.get("displayRecommendation") or "不詳")[:1024],
        inline=False,
    )
    embed.set_footer(
        text=(
            f"{image_count or len(message.attachments)} 張影像已送人工覆核；核准後才公開｜"
            f"{datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d %H:%M')}"
        )
    )
    await message.reply(embed=embed)


async def _run_antique_intake(
    message: discord.Message,
    attachments: list[discord.Attachment],
) -> None:
    try:
        prepared = await _download_and_prepare_images(attachments)
        payload, request_bytes = build_ingest_payload(
            prepared,
            ingest_secret=AP_INGEST_SECRET,
            caption=message.content or "無描述",
            message_id=str(message.id),
            channel_id=str(message.channel.id),
            user_id=str(message.author.id),
            user_name=message.author.display_name,
        )
        log.info(
            "[Antique] POST GAS msgId=%s images=%d requestBytes=%d compressedBytes=%d",
            message.id,
            len(prepared),
            request_bytes,
            sum(len(image.data) for image in prepared),
        )
        result = await _post_to_gas(payload)
        if not result.get("success"):
            error = str(result.get("error") or "未知錯誤")[:500]
            retry_safe = result.get("retrySafe") is True
            raise RuntimeError(f"GAS 編目失敗（retrySafe={retry_safe}）：{error}")

        await _send_bridge_result(message, result)
        await _set_terminal_reaction(message, COMPLETED_REACTION)
        log.info(
            "[Antique] 完成 msgId=%s artifactUuid=%s duplicate=%s",
            message.id,
            result.get("artifactUuid", ""),
            result.get("duplicate") is True,
        )

        if notion_enabled():
            try:
                analysis = result.get("analysis") if isinstance(result.get("analysis"), dict) else {}
                create_authentication_log(
                    title=analysis.get("itemName", "未命名器物"),
                    user=message.author.display_name,
                    gemini_judgment=(
                        f"分類：{analysis.get('category', '不詳')} | 斷代：{analysis.get('era', '不詳')}\n"
                        f"影像觀察：{str(analysis.get('features', '不詳'))[:800]}\n"
                        f"故事：{str(analysis.get('story', '不詳'))[:800]}"
                    ),
                    curator_status="未審",
                    notes=(
                        f"圖片：{result.get('fileUrl', '')}\nmsgId={message.id}\n"
                        f"artifactUuid={result.get('artifactUuid', '')}"
                    ),
                )
            except Exception as exc:
                log.warning("[notion] auth log failed: %s", exc)
    except Exception as err:
        await message.reply(f"**編目停止，未自動重送**\n{str(err)[:500]}")
        await _set_terminal_reaction(message, MANUAL_REVIEW_REACTION)
        log.error("[Antique] 錯誤 msgId=%s: %s", message.id, err, exc_info=True)


async def _process_antique_images(
    message: discord.Message,
    attachments: list[discord.Attachment],
) -> None:
    """Serialize intake to protect free-tier quotas and deterministic Sheet writes."""
    try:
        async with _intake_semaphore:
            await _run_antique_intake(message, attachments)
    finally:
        _active_message_ids.discard(message.id)


# ================================================================
# 入口
# ================================================================
def main():
    validate_bridge_config(BOT_TOKEN, GAS_DOPOST_URL, AP_INGEST_SECRET)
    if ENTERPRISE_SSL_BYPASS:
        apply_enterprise_ssl_bypass()
        log.warning("[SSL] AP_ENTERPRISE_SSL_BYPASS 已啟用")
    log.info("🏺 吉寶軒 Intake Bridge v3.0 啟動中...")
    log.info("   模式：Discord Gateway → local compression → GAS doPost")
    log.info("   按 Ctrl+C 停止")
    bot.run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
