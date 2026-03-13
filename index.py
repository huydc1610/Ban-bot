import discord
from discord.ext import commands
import asyncio
import os
import json
from discord import app_commands
from typing import Optional
import re
import time
from dotenv import load_dotenv
load_dotenv()

MAIN_GUILD_ID = discord.Object(id=1397175419664470031)
TARGET_ROLE_ID = 1442769995783475292
TARGET_CATEGORY_ID = 1442769574285283399
ALLOWED_ROLE_IDS = [
    1397185946541359214,
    1397191790381236304,
    1408419247163576330,
    1450851766911369337
]
ROLES_TO_REMOVE = [
    1434043875445702656,
    1408433140363432006,
    1397191419361230970,
    1408419247163576330,
    1397191790381236304,
    1463754309245337672,
    1462487968705937418,
]

DATA_FILE = "radao_data.json"

def load_radao_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_radao_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

radao_data = load_radao_data()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
temp_saved_roles = {}

def has_allowed_role(interaction: discord.Interaction) -> bool:
    return any(role.id in ALLOWED_ROLE_IDS for role in interaction.user.roles)

def convert_time(time_str):
    time_str = time_str.lower().replace(" ", "")
    total_seconds = 0
    matches = re.findall(r"(\d+)([dhms])", time_str)
    if not matches: return -1
    for val, unit in matches:
        val = int(val)
        if unit == 's': total_seconds += val
        elif unit == 'm': total_seconds += val * 60
        elif unit == 'h': total_seconds += val * 3600
        elif unit == 'd': total_seconds += val * 86400
    return total_seconds if total_seconds > 0 else -1

def parse_monkeys(guild: discord.Guild, monkeys: str) -> list[discord.Member]:
    members = []
    id_pattern = re.compile(r'<@!?(\d+)>')
    parts = re.split(r'[,\s]+', monkeys.strip())
    for part in parts:
        if not part: continue
        match = id_pattern.match(part)
        member_id = int(match.group(1)) if match else (int(part) if part.isdigit() else None)
        if member_id:
            member = guild.get_member(member_id)
            if member and member not in members: members.append(member)
    return members

async def restore_roles(guild, member):
    if member.id in temp_saved_roles:
        role_ids = temp_saved_roles[member.id]
        roles_to_add = [guild.get_role(rid) for rid in role_ids if guild.get_role(rid)]
        if roles_to_add:
            try: await member.add_roles(*roles_to_add)
            except: pass
        del temp_saved_roles[member.id]

def add_radao_member(member_id, reason, end_timestamp, saved_roles):
    radao_data[str(member_id)] = {
        "reason": reason,
        "end_timestamp": end_timestamp,
        "saved_roles": saved_roles
    }
    save_radao_data(radao_data)

def remove_radao_member(member_id):
    if str(member_id) in radao_data:
        del radao_data[str(member_id)]
        save_radao_data(radao_data)

async def perform_radao(interaction, member, seconds, period, reason):
    guild = interaction.guild
    role_radao = guild.get_role(TARGET_ROLE_ID)
    category = guild.get_channel(TARGET_CATEGORY_ID)

    if not role_radao or not category: return

    roles_to_remove = [r for r in member.roles if r.id in ROLES_TO_REMOVE]
    saved_role_ids = [r.id for r in roles_to_remove]
    if roles_to_remove:
        temp_saved_roles[member.id] = saved_role_ids
        try: await member.remove_roles(*roles_to_remove, reason="Radao")
        except: pass

    try:
        await member.add_roles(role_radao, reason=reason)
        end_time_timestamp = int(time.time() + seconds)
        discord_timestamp = f"<t:{end_time_timestamp}:R>"
        full_date_timestamp = f"<t:{end_time_timestamp}:F>"

        add_radao_member(member.id, reason, end_time_timestamp, saved_role_ids)

        channel = await guild.create_text_channel(
            name=f"dao-khi-{member.display_name}",
            category=category,
            topic=f"ID: {member.id} | Ra đảo vì: {reason}"
        )

        await channel.set_permissions(member, read_messages=True, send_messages=True)
        await channel.send(f"Chào mừng {member.mention} đến với đảo! Về bờ sau {discord_timestamp} ({full_date_timestamp}).")
        try:
            await channel.send(f"Lý do ra đảo: **{reason}**")
            await channel.send("Ngồi đây bị Rick Lăn nhé :Đ!")
            await channel.send("https://tenor.com/view/rickroll-roll-rick-never-gonna-give-you-up-never-gonna-gif-22954713")
        except Exception:
            await channel.send(f"Lần này méo có rick roll may đấy")

        await asyncio.sleep(seconds)

        member = guild.get_member(member.id)
        if member and role_radao in member.roles:
            await member.remove_roles(role_radao)
            await restore_roles(guild, member)
        remove_radao_member(member.id)
        if channel: await channel.delete()
    except Exception as e:
        print(f"Lỗi quy trình: {e}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------ BẮT ĐẦU ĐỒNG BỘ LỆNH ------')
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync(guild=None)
    print(">> Đã xóa sạch lệnh Global cũ (Fix lỗi trùng lệnh).")
    try:
        synced = await bot.tree.sync(guild=MAIN_GUILD_ID)
        print(f">> Server Chính (ID: {MAIN_GUILD_ID.id}): Đã sync {len(synced)} lệnh (/radao, /vebo).")
    except Exception as e:
        print(f"!! Lỗi Sync Server Chính: {e}")

    guild = bot.get_guild(MAIN_GUILD_ID.id)
    if guild:
        now = int(time.time())
        for member_id_str, info in list(radao_data.items()):
            member_id = int(member_id_str)
            remaining = info["end_timestamp"] - now
            member = guild.get_member(member_id)
            if remaining <= 0:
                if member:
                    role_radao = guild.get_role(TARGET_ROLE_ID)
                    if role_radao and role_radao in member.roles:
                        await member.remove_roles(role_radao)
                    saved = info.get("saved_roles", [])
                    roles_to_add = [guild.get_role(rid) for rid in saved if guild.get_role(rid)]
                    if roles_to_add:
                        try: await member.add_roles(*roles_to_add)
                        except: pass
                    cat = guild.get_channel(TARGET_CATEGORY_ID)
                    if cat:
                        for c in cat.text_channels:
                            if str(member_id) in (c.topic or "") or str(member_id) in c.name:
                                await c.delete()
                remove_radao_member(member_id)
            else:
                if member:
                    role_radao = guild.get_role(TARGET_ROLE_ID)
                    if role_radao and role_radao not in member.roles:
                        await member.add_roles(role_radao)
                asyncio.create_task(resume_radao_timer(guild, member_id, remaining))
async def resume_radao_timer(guild, member_id, remaining_seconds):
    await asyncio.sleep(remaining_seconds)
    member = guild.get_member(member_id)
    if member:
        role_radao = guild.get_role(TARGET_ROLE_ID)
        if role_radao and role_radao in member.roles:
            await member.remove_roles(role_radao)
        info = radao_data.get(str(member_id), {})
        saved = info.get("saved_roles", [])
        roles_to_add = [guild.get_role(rid) for rid in saved if guild.get_role(rid)]
        if roles_to_add:
            try: await member.add_roles(*roles_to_add)
            except: pass
        cat = guild.get_channel(TARGET_CATEGORY_ID)
        if cat:
            for c in cat.text_channels:
                if str(member_id) in (c.topic or "") or str(member_id) in c.name:
                    await c.delete()
    remove_radao_member(member_id)

@bot.event
async def on_member_join(member: discord.Member):
    member_id_str = str(member.id)
    if member_id_str in radao_data:
        info = radao_data[member_id_str]
        guild = member.guild
        role_radao = guild.get_role(TARGET_ROLE_ID)
        now = int(time.time())
        remaining = info["end_timestamp"] - now

        if remaining <= 0:
            remove_radao_member(member.id)
            return

        if role_radao:
            try: await member.add_roles(role_radao, reason="Rejoin - vẫn đang ra đảo")
            except: pass

        roles_to_remove = [r for r in member.roles if r.id in ROLES_TO_REMOVE]
        if roles_to_remove:
            try: await member.remove_roles(*roles_to_remove, reason="Rejoin - radao")
            except: pass

@bot.tree.command(name="radao", description="Cho khỉ ra đảo.", guild=MAIN_GUILD_ID)
@app_commands.describe(monkeys='Tag hoặc ID', period='VD: 10m, 1h', reason='Lý do')
async def radao(interaction: discord.Interaction, monkeys: str, period: str, reason: str = "Thằng ban thích thì cho thôi"):
    if not has_allowed_role(interaction):
        return await interaction.response.send_message("Bạn không có quyền dùng lệnh này.", ephemeral=True)

    seconds = convert_time(period)
    if seconds == -1: return await interaction.response.send_message("Sai thời gian (vd: 10m, 1h).", ephemeral=True)

    targets = parse_monkeys(interaction.guild, monkeys)
    if not targets: return await interaction.response.send_message("Không tìm thấy người dùng.", ephemeral=True)

    await interaction.response.defer()
    msg = []
    for m in targets:
        if m.top_role >= interaction.user.top_role:
            continue
        asyncio.create_task(perform_radao(interaction, m, seconds, period, reason))
        msg.append(f"Bonk🔨 bà zà mài {m.mention} ra đảo trong {period} lý do: {reason}.")

    await interaction.followup.send("\n".join(msg))

@bot.tree.command(name="vebo", description="Đưa khỉ về bờ.", guild=MAIN_GUILD_ID)
async def vebo(interaction: discord.Interaction, monkeys: str):
    if not has_allowed_role(interaction):
        return await interaction.response.send_message("Bạn không có quyền dùng lệnh này.", ephemeral=True)
    targets = parse_monkeys(interaction.guild, monkeys)
    if not targets: return await interaction.response.send_message("Không tìm thấy ai.", ephemeral=True)

    await interaction.response.defer()
    role = interaction.guild.get_role(TARGET_ROLE_ID)
    msg = []
    for m in targets:
        if role in m.roles:
            await m.remove_roles(role)
            await restore_roles(interaction.guild, m)
            remove_radao_member(m.id)
            msg.append(f"Đã về bờ: {m.mention}")
            cat = interaction.guild.get_channel(TARGET_CATEGORY_ID)
            if cat:
                for c in cat.text_channels:
                    if str(m.id) in (c.topic or "") or str(m.id) in c.name:
                        await c.delete()
        else:
            msg.append(f"{m.mention} không ở đảo.")
    await interaction.followup.send("\n".join(msg))
if __name__ == "__main__":
    token = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Missing bot token in environment (TOKEN or DISCORD_TOKEN)")
    bot.run(token)

