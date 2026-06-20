import discord
from discord.ext import commands
import asyncio
import os
import time
from dotenv import load_dotenv

import importlib
import config

load_dotenv()

CONFIG_RELOAD_INTERVAL_SECONDS = float(os.getenv("CONFIG_RELOAD_INTERVAL_SECONDS", "2"))
last_mtime = os.path.getmtime("config.py") if os.path.exists("config.py") else 0
last_config_check = 0.0
commands_synced = False

# ── Bot setup ────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.tree.interaction_check
async def auto_reload_config(interaction: discord.Interaction):
    global last_mtime, last_config_check
    now = time.monotonic()
    if now - last_config_check < CONFIG_RELOAD_INTERVAL_SECONDS:
        return True
    last_config_check = now

    try:
        if os.path.exists("config.py"):
            current_mtime = os.path.getmtime("config.py")
            if current_mtime > last_mtime:
                importlib.reload(config)
                last_mtime = current_mtime
                print("Đã tự động tải lại config.py (hot reload).")
    except Exception as e:
        print(f"Lỗi khi auto-reload config.py: {e}")
    return True

# ── Cogs to load ─────────────────────────────────────────────────────
INITIAL_COGS = [
    "cogs.radao",
    "cogs.nhapkho",
]


async def load_cogs():
    for cog in INITIAL_COGS:
        try:
            await bot.load_extension(cog)
            print(f"  ✓ Loaded: {cog}")
        except Exception as e:
            print(f"  ✗ Failed to load {cog}: {e}")


# ── Events ───────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    global commands_synced
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    if commands_synced:
        print("Slash commands already synced; skipping resync.")
        return

    print("------ BẮT ĐẦU ĐỒNG BỘ LỆNH ------")

    if os.getenv("CLEAR_GLOBAL_COMMANDS_ON_STARTUP") == "1":
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync(guild=None)
        print(">> Đã xóa sạch lệnh Global cũ.")

    try:
        synced = await bot.tree.sync(guild=config.MAIN_GUILD_ID)
        print(
            f">> Server Chính (ID: {config.MAIN_GUILD_ID.id}): Đã sync {len(synced)} lệnh."
        )
        commands_synced = True
    except Exception as e:
        print(f"!! Lỗi Sync Server Chính: {e}")

    print("--------------------------------------")


# ── Entry point ──────────────────────────────────────────────────────
async def main():
    async with bot:
        await load_cogs()
        token = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN")
        if not token:
            raise SystemExit("Missing bot token in environment (TOKEN or DISCORD_TOKEN)")
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
