import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import json
import re
import time

import config

DATA_FILE = os.path.join(config.DATA_DIR, "radao_data.json")


# ── Data helpers ─────────────────────────────────────────────────────
def load_radao_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_radao_data(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


# ── Utility helpers ──────────────────────────────────────────────────
def has_allowed_role(interaction: discord.Interaction) -> bool:
    return any(role.id in config.ALLOWED_ROLE_IDS for role in interaction.user.roles)


def convert_time(time_str: str) -> int:
    time_str = time_str.lower().replace(" ", "")
    total_seconds = 0
    matches = re.findall(r"(\d+)([dhms])", time_str)
    if not matches:
        return -1
    for val, unit in matches:
        val = int(val)
        if unit == "s":
            total_seconds += val
        elif unit == "m":
            total_seconds += val * 60
        elif unit == "h":
            total_seconds += val * 3600
        elif unit == "d":
            total_seconds += val * 86400
    return total_seconds if total_seconds > 0 else -1


def parse_monkeys(guild: discord.Guild, monkeys: str) -> list[discord.Member]:
    members = []
    id_pattern = re.compile(r"<@!?(\d+)>")
    parts = re.split(r"[,\s]+", monkeys.strip())
    for part in parts:
        if not part:
            continue
        match = id_pattern.match(part)
        member_id = (
            int(match.group(1)) if match else (int(part) if part.isdigit() else None)
        )
        if member_id:
            member = guild.get_member(member_id)
            if member and member not in members:
                members.append(member)
    return members


# ── Cog ──────────────────────────────────────────────────────────────
class RadaoCog(commands.Cog):
    """Cog quản lý lệnh /radao (cho khỉ ra đảo) và /vebo (đưa khỉ về bờ)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.radao_data: dict = load_radao_data()
        self.temp_saved_roles: dict[int, list[int]] = {}

    # ── Data management ──────────────────────────────────────────────
    def add_radao_member(
        self, member_id: int, reason: str, end_timestamp: int, saved_roles: list[int]
    ):
        self.radao_data[str(member_id)] = {
            "reason": reason,
            "end_timestamp": end_timestamp,
            "saved_roles": saved_roles,
        }
        save_radao_data(self.radao_data)

    def remove_radao_member(self, member_id: int):
        if str(member_id) in self.radao_data:
            del self.radao_data[str(member_id)]
            save_radao_data(self.radao_data)

    # ── Role helpers ─────────────────────────────────────────────────
    async def restore_roles(self, guild: discord.Guild, member: discord.Member):
        if member.id in self.temp_saved_roles:
            role_ids = self.temp_saved_roles[member.id]
            roles_to_add = [
                guild.get_role(rid) for rid in role_ids if guild.get_role(rid)
            ]
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add)
                except Exception:
                    pass
            del self.temp_saved_roles[member.id]

    # ── Core radao logic ─────────────────────────────────────────────
    async def perform_radao(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        seconds: int,
        period: str,
        reason: str,
    ):
        guild = interaction.guild
        role_radao = guild.get_role(config.TARGET_ROLE_ID)
        category = guild.get_channel(config.TARGET_CATEGORY_ID)

        if not role_radao or not category:
            return

        roles_to_remove = [r for r in member.roles if r.id in config.ROLES_TO_REMOVE]
        saved_role_ids = [r.id for r in roles_to_remove]
        if roles_to_remove:
            self.temp_saved_roles[member.id] = saved_role_ids
            try:
                await member.remove_roles(*roles_to_remove, reason="Radao")
            except Exception:
                pass

        try:
            await member.add_roles(role_radao, reason=reason)
            if member.voice and member.voice.channel:
                try:
                    await member.move_to(None, reason=f"Ra đảo: {reason}")
                except Exception:
                    pass

            end_time_timestamp = int(time.time() + seconds)
            discord_timestamp = f"<t:{end_time_timestamp}:R>"
            full_date_timestamp = f"<t:{end_time_timestamp}:F>"

            self.add_radao_member(member.id, reason, end_time_timestamp, saved_role_ids)

            channel = await guild.create_text_channel(
                name=f"dao-khi-{member.display_name}",
                category=category,
                topic=f"ID: {member.id} | Ra đảo vì: {reason}",
            )

            await channel.set_permissions(
                member, read_messages=True, send_messages=True
            )
            # Ẩn channel đảo với người có role nhập kho
            role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
            if role_nhapkho:
                await channel.set_permissions(
                    role_nhapkho, read_messages=False
                )
            await channel.send(
                f"Chào mừng {member.mention} đến với đảo! Về bờ sau {discord_timestamp} ({full_date_timestamp})."
            )
            try:
                await channel.send(f"Lý do ra đảo: **{reason}**")
                await channel.send("Ngồi đây bị Rick Lăn nhé :Đ!")
                await channel.send(
                    "https://tenor.com/view/rickroll-roll-rick-never-gonna-give-you-up-never-gonna-gif-22954713"
                )
            except Exception:
                await channel.send("Lần này méo có rick roll may đấy")

            await asyncio.sleep(seconds)

            member = guild.get_member(member.id)
            if member and role_radao in member.roles:
                await member.remove_roles(role_radao)
                await self.restore_roles(guild, member)
            self.remove_radao_member(member.id)
            if channel:
                await channel.delete()
        except Exception as e:
            print(f"Lỗi quy trình: {e}")

    async def resume_radao_timer(
        self, guild: discord.Guild, member_id: int, remaining_seconds: int
    ):
        await asyncio.sleep(remaining_seconds)
        member = guild.get_member(member_id)
        if member:
            role_radao = guild.get_role(config.TARGET_ROLE_ID)
            if role_radao and role_radao in member.roles:
                await member.remove_roles(role_radao)
            info = self.radao_data.get(str(member_id), {})
            saved = info.get("saved_roles", [])
            roles_to_add = [
                guild.get_role(rid) for rid in saved if guild.get_role(rid)
            ]
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add)
                except Exception:
                    pass
            cat = guild.get_channel(config.TARGET_CATEGORY_ID)
            if cat:
                for c in cat.text_channels:
                    if str(member_id) in (c.topic or "") or str(member_id) in c.name:
                        await c.delete()
        self.remove_radao_member(member_id)

    # ── Events (Listeners) ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"[RadaoCog] Loaded — đang kiểm tra radao data...")
        guild = self.bot.get_guild(config.MAIN_GUILD_ID.id)
        if not guild:
            return

        now = int(time.time())
        for member_id_str, info in list(self.radao_data.items()):
            member_id = int(member_id_str)
            remaining = info["end_timestamp"] - now
            member = guild.get_member(member_id)

            if remaining <= 0:
                # Hết hạn — gỡ role & xóa channel
                if member:
                    role_radao = guild.get_role(config.TARGET_ROLE_ID)
                    if role_radao and role_radao in member.roles:
                        await member.remove_roles(role_radao)
                    saved = info.get("saved_roles", [])
                    roles_to_add = [
                        guild.get_role(rid) for rid in saved if guild.get_role(rid)
                    ]
                    if roles_to_add:
                        try:
                            await member.add_roles(*roles_to_add)
                        except Exception:
                            pass
                    cat = guild.get_channel(config.TARGET_CATEGORY_ID)
                    if cat:
                        for c in cat.text_channels:
                            if (
                                str(member_id) in (c.topic or "")
                                or str(member_id) in c.name
                            ):
                                await c.delete()
                self.remove_radao_member(member_id)
            else:
                # Còn hạn — đảm bảo role và resume timer
                if member:
                    role_radao = guild.get_role(config.TARGET_ROLE_ID)
                    if role_radao and role_radao not in member.roles:
                        await member.add_roles(role_radao)
                asyncio.create_task(
                    self.resume_radao_timer(guild, member_id, remaining)
                )

        print(f"[RadaoCog] Đã xử lý {len(self.radao_data)} radao entries.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        member_id_str = str(member.id)
        if member_id_str not in self.radao_data:
            return

        info = self.radao_data[member_id_str]
        guild = member.guild
        role_radao = guild.get_role(config.TARGET_ROLE_ID)
        now = int(time.time())
        remaining = info["end_timestamp"] - now

        if remaining <= 0:
            self.remove_radao_member(member.id)
            return

        if role_radao:
            try:
                await member.add_roles(role_radao, reason="Rejoin - vẫn đang ra đảo")
            except Exception:
                pass

        roles_to_remove = [r for r in member.roles if r.id in config.ROLES_TO_REMOVE]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Rejoin - radao")
            except Exception:
                pass

    # ── Slash Commands ───────────────────────────────────────────────
    @app_commands.command(
        name="radao", description="Cho khỉ ra đảo."
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    @app_commands.describe(
        monkeys="Tag hoặc ID", period="VD: 10m, 1h", reason="Lý do"
    )
    async def radao(
        self,
        interaction: discord.Interaction,
        monkeys: str,
        period: str,
        reason: str = "Thằng ban thích thì cho thôi",
    ):
        if not has_allowed_role(interaction):
            return await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )

        seconds = convert_time(period)
        if seconds == -1:
            return await interaction.response.send_message(
                "Sai thời gian (vd: 10m, 1h).", ephemeral=True
            )

        targets = parse_monkeys(interaction.guild, monkeys)
        if not targets:
            return await interaction.response.send_message(
                "Không tìm thấy người dùng.", ephemeral=True
            )

        await interaction.response.defer()
        msg = []
        for m in targets:
            if m.id == interaction.user.id:
                if interaction.user.id != config.SELF_BAN_ALLOWED_ID:
                    msg.append("Đừng tự bắn vào chân thế chứ bro")
                    continue
            else:
                effective_target_roles = [
                    r for r in m.roles if r.id not in config.IGNORED_BANNED_ROLES
                ]
                effective_top_role = (
                    effective_target_roles[-1]
                    if effective_target_roles
                    else m.roles[0]
                )
                if effective_top_role > interaction.user.top_role:
                    msg.append(f"Bạn không thể timeout {m.mention} — người này có quyền cao hơn bạn.")
                    continue
                if effective_top_role == interaction.user.top_role:
                    msg.append(f"Không thể timeout {m.mention} — người này có cùng role với bạn.")
                    continue
            asyncio.create_task(
                self.perform_radao(interaction, m, seconds, period, reason)
            )
            msg.append(
                f"Bonk🔨 bà zà mài {m.mention} ra đảo trong {period} lý do: {reason}."
            )

        await interaction.followup.send("\n".join(msg))

    @app_commands.command(
        name="vebo", description="Đưa khỉ về bờ."
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    async def vebo(self, interaction: discord.Interaction, monkeys: str):
        if not has_allowed_role(interaction):
            return await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )

        targets = parse_monkeys(interaction.guild, monkeys)
        if not targets:
            return await interaction.response.send_message(
                "Không tìm thấy ai.", ephemeral=True
            )

        await interaction.response.defer()
        role = interaction.guild.get_role(config.TARGET_ROLE_ID)
        msg = []
        for m in targets:
            if role in m.roles:
                await m.remove_roles(role)
                await self.restore_roles(interaction.guild, m)
                self.remove_radao_member(m.id)
                msg.append(f"Đã về bờ: {m.mention}")
                cat = interaction.guild.get_channel(config.TARGET_CATEGORY_ID)
                if cat:
                    for c in cat.text_channels:
                        if (
                            str(m.id) in (c.topic or "")
                            or str(m.id) in c.name
                        ):
                            await c.delete()
            else:
                msg.append(f"{m.mention} không ở đảo.")
        await interaction.followup.send("\n".join(msg))


# ── Setup function (required for cog loading) ───────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(RadaoCog(bot))
