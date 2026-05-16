import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import json
import re
import time

import config

DATA_FILE = os.path.join(config.DATA_DIR, "nhapkho_data.json")


# ── Data helpers ─────────────────────────────────────────────────────
def load_nhapkho_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_nhapkho_data(data: dict):
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
class NhapKhoCog(commands.Cog):
    """Cog quản lý lệnh /nhapkho và /xuatkho — gỡ role và gán role kho."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.nhapkho_data: dict = load_nhapkho_data()
        self.temp_saved_roles: dict[int, list[int]] = {}

    # ── Data management ──────────────────────────────────────────────
    def add_nhapkho_member(
        self, member_id: int, reason: str, end_timestamp: int, saved_roles: list[int],
        log_message_id: int = None,
    ):
        self.nhapkho_data[str(member_id)] = {
            "reason": reason,
            "end_timestamp": end_timestamp,
            "saved_roles": saved_roles,
            "log_message_id": log_message_id,
        }
        save_nhapkho_data(self.nhapkho_data)

    def remove_nhapkho_member(self, member_id: int):
        if str(member_id) in self.nhapkho_data:
            del self.nhapkho_data[str(member_id)]
            save_nhapkho_data(self.nhapkho_data)

    # ── Role helpers ─────────────────────────────────────────────────
    async def restore_roles(self, guild: discord.Guild, member: discord.Member):
        # Ưu tiên temp (in-memory), fallback sang persistent data
        if member.id in self.temp_saved_roles:
            role_ids = self.temp_saved_roles[member.id]
            del self.temp_saved_roles[member.id]
        else:
            info = self.nhapkho_data.get(str(member.id), {})
            role_ids = info.get("saved_roles", [])

        roles_to_add = [
            guild.get_role(rid) for rid in role_ids if guild.get_role(rid)
        ]
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add)
            except Exception:
                pass

    # ── Core nhapkho logic ───────────────────────────────────────────
    async def perform_nhapkho(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        seconds: int,
        period: str,
        reason: str,
    ):
        guild = interaction.guild
        role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)

        if not role_nhapkho:
            return

        # Gỡ các role trong ROLES_TO_REMOVE và lưu lại
        roles_to_remove = [r for r in member.roles if r.id in config.ROLES_TO_REMOVE]
        saved_role_ids = [r.id for r in roles_to_remove]
        if roles_to_remove:
            self.temp_saved_roles[member.id] = saved_role_ids
            try:
                await member.remove_roles(*roles_to_remove, reason="Hôm nay đẹp trời nên thích thì cho mài vô chuồng thôi")
            except Exception:
                pass

        try:
            # Gán role nhập kho
            await member.add_roles(role_nhapkho, reason=reason)

            # Kick khỏi voice nếu đang trong voice
            if member.voice and member.voice.channel:
                try:
                    await member.move_to(None, reason=f"Nhập kho: {reason}")
                except Exception:
                    pass

            end_time_timestamp = int(time.time() + seconds)
            discord_timestamp = f"<t:{end_time_timestamp}:R>"
            full_date_timestamp = f"<t:{end_time_timestamp}:F>"

            # Gửi thông báo vào channel log
            log_msg = None
            log_channel = guild.get_channel(config.NHAPKHO_LOG_CHANNEL_ID)
            if log_channel:
                log_msg = await log_channel.send(
                    f"{member.mention} vào chuồng trong {period} (ra chuồng sau {discord_timestamp}) - lý do: {reason}"
                )

            self.add_nhapkho_member(
                member.id, reason, end_time_timestamp, saved_role_ids,
                log_message_id=log_msg.id if log_msg else None,
            )

            # Chờ hết thời gian
            await asyncio.sleep(seconds)

            # Xuất kho — xóa tin nhắn log, gỡ role, trả role
            await self._delete_log_message(guild, member.id)
            member = guild.get_member(member.id)
            if member:
                if role_nhapkho in member.roles:
                    await member.remove_roles(role_nhapkho)
                await self.restore_roles(guild, member)
            self.remove_nhapkho_member(member.id)
        except Exception as e:
            print(f"[NhapKho] Lỗi quy trình: {e}")

    async def _delete_log_message(self, guild: discord.Guild, member_id: int):
        """Xóa tin nhắn log trong channel thông báo."""
        info = self.nhapkho_data.get(str(member_id), {})
        log_msg_id = info.get("log_message_id")
        if log_msg_id:
            log_channel = guild.get_channel(config.NHAPKHO_LOG_CHANNEL_ID)
            if log_channel:
                try:
                    log_msg = await log_channel.fetch_message(log_msg_id)
                    await log_msg.delete()
                except Exception:
                    pass

    async def resume_nhapkho_timer(
        self, guild: discord.Guild, member_id: int, remaining_seconds: int
    ):
        await asyncio.sleep(remaining_seconds)
        await self._delete_log_message(guild, member_id)
        member = guild.get_member(member_id)
        if member:
            role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
            if role_nhapkho and role_nhapkho in member.roles:
                await member.remove_roles(role_nhapkho)
            info = self.nhapkho_data.get(str(member_id), {})
            saved = info.get("saved_roles", [])
            roles_to_add = [
                guild.get_role(rid) for rid in saved if guild.get_role(rid)
            ]
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add)
                except Exception:
                    pass
        self.remove_nhapkho_member(member_id)

    # ── Events (Listeners) ───────────────────────────────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"[NhapKhoCog] Loaded — đang kiểm tra nhapkho data...")
        guild = self.bot.get_guild(config.MAIN_GUILD_ID.id)
        if not guild:
            return

        now = int(time.time())
        for member_id_str, info in list(self.nhapkho_data.items()):
            member_id = int(member_id_str)
            remaining = info["end_timestamp"] - now
            member = guild.get_member(member_id)

            if remaining <= 0:
                # Hết hạn — xóa log, gỡ role nhập kho & trả role
                await self._delete_log_message(guild, member_id)
                if member:
                    role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
                    if role_nhapkho and role_nhapkho in member.roles:
                        await member.remove_roles(role_nhapkho)
                    saved = info.get("saved_roles", [])
                    roles_to_add = [
                        guild.get_role(rid) for rid in saved if guild.get_role(rid)
                    ]
                    if roles_to_add:
                        try:
                            await member.add_roles(*roles_to_add)
                        except Exception:
                            pass
                self.remove_nhapkho_member(member_id)
            else:
                # Còn hạn — đảm bảo role và resume timer
                if member:
                    role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
                    if role_nhapkho and role_nhapkho not in member.roles:
                        await member.add_roles(role_nhapkho)
                asyncio.create_task(
                    self.resume_nhapkho_timer(guild, member_id, remaining)
                )

        print(f"[NhapKhoCog] Đã xử lý {len(self.nhapkho_data)} nhapkho entries.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        member_id_str = str(member.id)
        if member_id_str not in self.nhapkho_data:
            return

        info = self.nhapkho_data[member_id_str]
        guild = member.guild
        role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
        now = int(time.time())
        remaining = info["end_timestamp"] - now

        if remaining <= 0:
            self.remove_nhapkho_member(member.id)
            return

        if role_nhapkho:
            try:
                await member.add_roles(role_nhapkho, reason="Rejoin - vẫn đang nhập kho")
            except Exception:
                pass

        roles_to_remove = [r for r in member.roles if r.id in config.ROLES_TO_REMOVE]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Rejoin - nhapkho")
            except Exception:
                pass

    # ── Slash Commands ───────────────────────────────────────────────
    @app_commands.command(
        name="nhapkho", description="Đưa một hoặc nhiều con khỉ vào chuồng."
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    @app_commands.describe(
        monkeys="Tag hoặc ID", period="VD: 10m, 1h", reason="Lý do"
    )
    async def nhapkho(
        self,
        interaction: discord.Interaction,
        monkeys: str,
        period: str,
        reason: str = "Nhập kho",
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
                self.perform_nhapkho(interaction, m, seconds, period, reason)
            )
            msg.append(
                f"{m.mention} đã bị gửi vào vườn thú trong {period} — lý do: {reason}."
            )

        await interaction.followup.send("\n".join(msg))

    @app_commands.command(
        name="xuatkho", description="Xuất chuồng thôi."
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    async def xuatkho(self, interaction: discord.Interaction, monkeys: str):
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
        role = interaction.guild.get_role(config.NHAPKHO_ROLE_ID)
        msg = []
        for m in targets:
            if role in m.roles:
                await m.remove_roles(role)
                await self.restore_roles(interaction.guild, m)
                await self._delete_log_message(interaction.guild, m.id)
                self.remove_nhapkho_member(m.id)
                msg.append(f"{m.mention} đã được thả về tự nhiên.")
            else:
                msg.append(f"{m.mention} không ở trong vườn thú.")
        await interaction.followup.send("\n".join(msg))


# ── Setup function (required for cog loading) ───────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(NhapKhoCog(bot))
