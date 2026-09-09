import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import sys
import time
import traceback
from dotenv import load_dotenv

import importlib
import config

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

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


bot.tree.interaction_check = auto_reload_config


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    print("Unhandled app command error:")
    traceback.print_exception(type(error), error, error.__traceback__)
    message = "Lệnh bị lỗi khi xử lý. Kiểm tra log bot để xem chi tiết."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except Exception:
        traceback.print_exc()

# ── Cogs to load ─────────────────────────────────────────────────────
INITIAL_COGS = [
    "cogs.radao",
    "cogs.nhapkho",
    "cogs.autoban",
    "cogs.autokick",
    "cogs.emoji",
    "cogs.sticker",
]


async def load_cogs():
    for cog in INITIAL_COGS:
        try:
            await bot.load_extension(cog)
            print(f"  OK Loaded: {cog}")
        except Exception as e:
            print(f"  ERR Failed to load {cog}: {e}")


# ── Events ───────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    global commands_synced
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    if commands_synced:
        print("Slash commands already synced; skipping resync.")
        return

    print("------ BẮT ĐẦU ĐỒNG BỘ LỆNH ------")

    if os.getenv("CLEAR_GLOBAL_COMMANDS_ON_STARTUP", "1") == "1":
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
