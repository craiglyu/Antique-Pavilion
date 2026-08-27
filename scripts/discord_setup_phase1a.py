"""
scripts/discord_setup_phase1a.py — AP Discord Phase 1A Setup（一次性執行）
================================================================
執行方式（WSL2）：
  cd /mnt/c/Users/A50529/Desktop/Craig/Antique\ Digital\ Pavilion
  python scripts/discord_setup_phase1a.py

動作：
  1. 建立 Discord Category 分組（若不存在）
  2. 重命名現有頻道：ap-web-design → ap-design, ap-web-dev → ap-frontend
  3. 新增 Phase 1A 頻道：
       council-topics, council-meetings, council-decisions
       ap-backend, ap-sre, ap-alerts
  4. 將現有頻道整理至對應 Category
  5. 印出新建頻道 ID（貼到 .env.antique）

需要：DISCORD_ORG_BOT_TOKEN 具備 Manage Channels 權限
版本：v1.0 (2026-04-27)
"""

import asyncio
import os
import ssl as _ssl
from pathlib import Path

# 企業 SSL Proxy bypass
_orig_ssl = _ssl.create_default_context
def _no_verify_ssl(*a, **kw):
    ctx = _orig_ssl(*a, **kw)
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    return ctx
_ssl.create_default_context = _no_verify_ssl

import discord
from discord.ext import commands

# ── Config ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent

def _load_env(f: Path) -> dict:
    env = {}
    if f.exists():
        for line in f.read_text("utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if v})
    return env

_ENV = _load_env(PROJECT_ROOT / ".env.antique")
BOT_TOKEN = _ENV.get("DISCORD_ORG_BOT_TOKEN", "")
GUILD_ID  = 1495279821469782026

# ── Phase 1A Layout ───────────────────────────────────────────────────────────
# 格式：(category 名稱, [頻道名稱列表])
# 已存在的頻道：只移至正確 category，不重建
# 新頻道：建立在對應 category 下

PHASE_1A_LAYOUT = [
    ("📋 Council 議事", [
        "council-topics",       # 新增：議題池
        "council-meetings",     # 新增：議事 thread 工作區
        "council-decisions",    # 新增：待簽核提案 + 已決議
    ]),
    ("🏺 Antique Pipeline", [
        "antique-analysis",     # 已存在：骨董鑑定主頻道
    ]),
    ("🎨 Product 產品", [
        "ap-ux",                # 新增（Phase 1B 啟用，先建頻道佔位）
        "ap-design",            # 由 ap-web-design 改名而來
        "ap-frontend",          # 由 ap-web-dev 改名而來
        "ap-backend",           # 新增：GAS / Bot 後端
    ]),
    ("📝 Content 內容", [
        "ap-seo",               # 新增（Phase 1B 啟用，先建佔位）
        "ap-editor",            # 新增（Phase 1B 啟用，先建佔位）
        "ap-marketing",         # 已存在：社群/轉化
    ]),
    ("⚙️ Operations 維運", [
        "ap-sre",               # 新增：可靠性監控
        "ap-alerts",            # 新增：告警獨立頻道
    ]),
    ("📊 Strategy 策略", [
        "ap-feedback",          # 已存在：Feedback PM
    ]),
    ("🪪 Meta", [
        "ap-pm",                # 已存在：PM Agent
        "ap-decisions-log",     # 新增：append-only 決議歷史
    ]),
]

# 需要重命名的頻道：{舊名: 新名}
RENAMES = {
    "ap-web-design": "ap-design",
    "ap-web-dev":    "ap-frontend",
}

# ── Setup Logic ───────────────────────────────────────────────────────────────

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"\n[Setup] Bot 連線：{bot.user}")
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print(f"[Setup] ❌ 找不到 Guild {GUILD_ID}，請確認 Bot 已加入 Server")
        await bot.close()
        return
    print(f"[Setup] Guild：{guild.name} ({guild.id})\n")
    await run_setup(guild)
    await bot.close()


async def run_setup(guild: discord.Guild):
    created_ids: dict[str, int] = {}  # channel_name → id（用於輸出 .env 設定）

    # ── Step 1: 重命名頻道 ─────────────────────────────────────────────────────
    print("── Step 1: 重命名現有頻道 ──")
    for old_name, new_name in RENAMES.items():
        ch = discord.utils.get(guild.text_channels, name=old_name)
        if ch:
            await ch.edit(name=new_name)
            print(f"  ✅ #{old_name} → #{new_name}  (ID: {ch.id})")
        else:
            # 已改過或不存在
            existing = discord.utils.get(guild.text_channels, name=new_name)
            if existing:
                print(f"  ℹ️  #{new_name} 已存在 (ID: {existing.id})，略過")
            else:
                print(f"  ⚠️  #{old_name} 不存在，也沒找到 #{new_name}，請手動確認")

    # ── Step 2: 建立 Category + 頻道，整理位置 ───────────────────────────────
    print("\n── Step 2: 建立 Category 分組與頻道 ──")
    for cat_name, channel_names in PHASE_1A_LAYOUT:
        # 取得或建立 Category
        cat = discord.utils.get(guild.categories, name=cat_name)
        if not cat:
            cat = await guild.create_category(cat_name)
            print(f"\n  📁 [新建] Category：{cat_name}")
        else:
            print(f"\n  📁 [已有] Category：{cat_name}")

        for ch_name in channel_names:
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if ch:
                # 已存在：移至正確 Category
                if ch.category_id != cat.id:
                    await ch.edit(category=cat)
                    print(f"    → 移入 #{ch_name} (ID: {ch.id})")
                else:
                    print(f"    ✓  #{ch_name} 已在此 Category (ID: {ch.id})")
                created_ids[ch_name] = ch.id
            else:
                # 不存在：建立
                ch = await cat.create_text_channel(ch_name)
                print(f"    ✨ 新建 #{ch_name} (ID: {ch.id})")
                created_ids[ch_name] = ch.id

            await asyncio.sleep(0.3)   # Discord rate limit buffer

    # ── Step 3: 輸出 .env.antique 新增段 ─────────────────────────────────────
    print("\n" + "=" * 60)
    print("── Step 3: 貼到 .env.antique 的新設定 ──")
    print("=" * 60)

    ENV_KEY_MAP = {
        "council-topics":    "DISCORD_CHANNEL_COUNCIL_TOPICS",
        "council-meetings":  "DISCORD_CHANNEL_COUNCIL_MEETINGS",
        "council-decisions": "DISCORD_CHANNEL_COUNCIL_DECISIONS",
        "ap-ux":             "DISCORD_CHANNEL_AP_UX",
        "ap-backend":        "DISCORD_CHANNEL_AP_BACKEND",
        "ap-seo":            "DISCORD_CHANNEL_AP_SEO",
        "ap-editor":         "DISCORD_CHANNEL_AP_EDITOR",
        "ap-sre":            "DISCORD_CHANNEL_AP_SRE",
        "ap-alerts":         "DISCORD_CHANNEL_AP_ALERTS",
        "ap-decisions-log":  "DISCORD_CHANNEL_AP_DECISIONS_LOG",
    }

    env_output = []
    for ch_name, env_key in ENV_KEY_MAP.items():
        if ch_name in created_ids:
            env_output.append(f"{env_key}={created_ids[ch_name]}")

    print("\n".join(env_output))
    print("=" * 60)
    print("\n[Setup] ✅ Phase 1A Discord 架構設定完成！")
    print("請將上方設定貼到 .env.antique 後，重啟兩支 Bot。")


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "DISCORD_ORG_BOT_TOKEN 未設定於 .env.antique\n"
            "請先確認 ORG Bot Token 是否正確填入。"
        )
    print("[Setup] 連線中（執行完畢自動斷線）...")
    bot.run(BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
