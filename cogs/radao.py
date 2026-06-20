import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import json
import time

import config
from cogs.common import (
    apply_role_update,
    convert_time,
    effective_top_role,
    has_allowed_role,
    parse_monkeys,
    role_ids_to_roles,
)

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
    async def restore_roles(
        self,
        guild: discord.Guild,
        member: discord.Member,
        roles_to_remove: list[discord.Role] | None = None,
    ):
        if member.id in self.temp_saved_roles:
            role_ids = self.temp_saved_roles[member.id]
            del self.temp_saved_roles[member.id]
        else:
            info = self.radao_data.get(str(member.id), {})
            role_ids = info.get("saved_roles", [])

        roles_to_add = role_ids_to_roles(guild, role_ids)
        try:
            await apply_role_update(
                member,
                roles_to_add=roles_to_add,
                roles_to_remove=roles_to_remove or (),
                reason="Radao restore roles",
            )
        except Exception:
            pass

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

        roles_to_remove = [
            r for r in member.roles if r.id in config.ROLES_TO_REMOVE_ID_SET
        ]
        saved_role_ids = [r.id for r in roles_to_remove]
        if roles_to_remove:
            self.temp_saved_roles[member.id] = saved_role_ids

        try:
            await apply_role_update(
                member,
                roles_to_add=[role_radao],
                roles_to_remove=roles_to_remove,
                reason=reason,
            )
            if member.voice and member.voice.channel:
                try:
                    await member.move_to(None, reason=f"Ra đảo: {reason}")
                except Exception:
                    pass

            end_time_timestamp = int(time.time() + seconds)
            discord_timestamp = f"<t:{end_time_timestamp}:R>"
            full_date_timestamp = f"<t:{end_time_timestamp}:F>"

            self.add_radao_member(member.id, reason, end_time_timestamp, saved_role_ids)

            overwrites = dict(category.overwrites)
            overwrites[member] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            )
            role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
            if role_nhapkho:
                overwrites[role_nhapkho] = discord.PermissionOverwrite(
                    read_messages=False,
                )

            channel = await guild.create_text_channel(
                name=f"dao-khi-{member.display_name}",
                category=category,
                topic=f"ID: {member.id} | Ra đảo vì: {reason}",
                overwrites=overwrites,
            )

            try:
                await channel.send(
                    "\n".join(
                        [
                            f"Chào mừng {member.mention} đến với đảo! Về bờ sau {discord_timestamp} ({full_date_timestamp}).",
                            f"Lý do ra đảo: **{reason}**",
                            "Ngồi đây bị Rick Lăn nhé :Đ!",
                            "https://tenor.com/view/rickroll-roll-rick-never-gonna-give-you-up-never-gonna-gif-22954713",
                        ]
                    )
                )
            except Exception:
                await channel.send("Lần này méo có rick roll may đấy")

            await asyncio.sleep(seconds)

            member_id = member.id
            member = guild.get_member(member_id)
            if member and role_radao in member.roles:
                await self.restore_roles(guild, member, roles_to_remove=[role_radao])
            self.remove_radao_member(member_id)
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
            info = self.radao_data.get(str(member_id), {})
            saved = info.get("saved_roles", [])
            roles_to_add = role_ids_to_roles(guild, saved)
            roles_to_remove = [role_radao] if role_radao and role_radao in member.roles else []
            try:
                await apply_role_update(
                    member,
                    roles_to_add=roles_to_add,
                    roles_to_remove=roles_to_remove,
                    reason="Radao expired",
                )
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
                    saved = info.get("saved_roles", [])
                    roles_to_add = role_ids_to_roles(guild, saved)
                    roles_to_remove = [
                        role_radao
                    ] if role_radao and role_radao in member.roles else []
                    try:
                        await apply_role_update(
                            member,
                            roles_to_add=roles_to_add,
                            roles_to_remove=roles_to_remove,
                            reason="Radao expired",
                        )
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
                        try:
                            await apply_role_update(
                                member,
                                roles_to_add=[role_radao],
                                reason="Radao resume",
                            )
                        except Exception:
                            pass
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

        roles_to_remove = [
            r for r in member.roles if r.id in config.ROLES_TO_REMOVE_ID_SET
        ]
        if role_radao or roles_to_remove:
            try:
                await apply_role_update(
                    member,
                    roles_to_add=[role_radao] if role_radao else [],
                    roles_to_remove=roles_to_remove,
                    reason="Rejoin - vẫn đang ra đảo",
                )
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

        msg = []
        for m in targets:
            if m.id == interaction.user.id:
                if interaction.user.id != config.SELF_BAN_ALLOWED_ID:
                    msg.append("Đừng tự bắn vào chân thế chứ bro")
                    continue
            else:
                target_top_role = effective_top_role(m)
                if target_top_role > interaction.user.top_role:
                    msg.append(f"Bạn không thể timeout {m.mention} — người này có quyền cao hơn bạn.")
                    continue
                if target_top_role == interaction.user.top_role:
                    msg.append(f"Không thể timeout {m.mention} — người này có cùng role với bạn.")
                    continue
            asyncio.create_task(
                self.perform_radao(interaction, m, seconds, period, reason)
            )
            msg.append(
                f"Bonk🔨 bà zà mài {m.mention} ra đảo trong {period} lý do: {reason}."
            )

        await interaction.response.send_message("\n".join(msg))

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
                await self.restore_roles(interaction.guild, m, roles_to_remove=[role])
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
