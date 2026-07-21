import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import time

import config
from cogs.common import (
    apply_role_update,
    convert_time,
    duration_exceeds_discord_timestamp,
    effective_top_role,
    format_discord_end_time,
    format_duration_display,
    has_allowed_role,
    load_json_dict,
    parse_monkeys,
    role_ids_to_roles,
    roles_to_remove_ids,
    save_json_dict,
)

DATA_FILE = os.path.join(config.DATA_DIR, "nhapkho_data.json")


class NhapKhoNoticeView(discord.ui.LayoutView):
    PANEL_TITLE = "## THÔNG BÁO NHẬP KHO\n"

    def __init__(
        self,
        member: discord.Member,
        reason: str,
        *,
        duration_text: str,
        end_time_text: str,
    ):
        super().__init__(timeout=None)

        panel_text = (
            "### 👤 ĐỐI TƯỢNG\n"
            f"> {member.mention}\n"
            "### ⏳ HÃY CÙNG ĐẾM NGƯỢC\n"
            f"> **{duration_text}**\n"
            "### 📝 LÝ DO\n"
            f"> **{reason}**\n"
        )

        items = [
            discord.ui.TextDisplay(self.PANEL_TITLE),
            discord.ui.Separator(),
            discord.ui.TextDisplay(panel_text),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"-# Update <t:{int(time.time())}:f>"),
        ]

        container = discord.ui.Container(*items)
        self.add_item(container)


class NhapKhoCommandResultView(discord.ui.LayoutView):
    PANEL_TITLE = "## TIẾN HÀNH NHẬP KHO\n"

    def __init__(self, result_lines: list[str], *, duration_text: str, reason: str):
        super().__init__(timeout=None)

        result_text = "\n".join(f"> {line}" for line in result_lines)
        panel_text = (
            "### 👤 ĐỐI TƯỢNG\n"
            f"{result_text}\n"
            "### ⏳ THỜI GIAN\n"
            f"> **{duration_text}**\n"
            "### 📝 LÝ DO\n"
            f"> **{reason}**\n"
        )
        items = [
            discord.ui.TextDisplay(self.PANEL_TITLE),
            discord.ui.Separator(),
            discord.ui.TextDisplay(panel_text),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"-# Update <t:{int(time.time())}:f>"),
        ]

        container = discord.ui.Container(*items)
        self.add_item(container)


# ── Data helpers ─────────────────────────────────────────────────────
def load_nhapkho_data() -> dict:
    return load_json_dict(DATA_FILE)


def save_nhapkho_data(data: dict):
    save_json_dict(DATA_FILE, data)


# ── Cog ──────────────────────────────────────────────────────────────
class NhapKhoCog(commands.Cog):
    """Cog quản lý lệnh /nhapkho — gỡ role và gán role kho."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.nhapkho_data: dict = load_nhapkho_data()
        self.temp_saved_roles: dict[int, list[int]] = {}

    # ── Data management ──────────────────────────────────────────────
    def add_nhapkho_member(
        self, member_id: int, reason: str, end_timestamp: int | None, saved_roles: list[int],
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
    async def restore_roles(
        self,
        guild: discord.Guild,
        member: discord.Member,
        roles_to_remove: list[discord.Role] | None = None,
    ):
        # Ưu tiên temp (in-memory), fallback sang persistent data
        if member.id in self.temp_saved_roles:
            role_ids = self.temp_saved_roles[member.id]
            del self.temp_saved_roles[member.id]
        else:
            info = self.nhapkho_data.get(str(member.id), {})
            role_ids = info.get("saved_roles", [])

        roles_to_add = role_ids_to_roles(guild, role_ids)
        try:
            await apply_role_update(
                member,
                roles_to_add=roles_to_add,
                roles_to_remove=roles_to_remove or (),
                reason="Nhap kho restore roles",
            )
        except Exception:
            pass

    async def release_member(self, guild: discord.Guild, member: discord.Member) -> bool:
        role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
        if not role_nhapkho or role_nhapkho not in member.roles:
            return False

        await self.restore_roles(guild, member, roles_to_remove=[role_nhapkho])
        await self._delete_log_message(guild, member.id)
        self.remove_nhapkho_member(member.id)
        return True

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
        removable_role_ids = roles_to_remove_ids()
        roles_to_remove = [r for r in member.roles if r.id in removable_role_ids]
        saved_role_ids = [r.id for r in roles_to_remove]
        if roles_to_remove:
            self.temp_saved_roles[member.id] = saved_role_ids

        try:
            # Gán role nhập kho
            await apply_role_update(
                member,
                roles_to_add=[role_nhapkho],
                roles_to_remove=roles_to_remove,
                reason=reason,
            )

            # Kick khỏi voice nếu đang trong voice
            if member.voice and member.voice.channel:
                try:
                    await member.move_to(None, reason=f"Nhập kho: {reason}")
                except Exception:
                    pass

            now = int(time.time())
            permanent = duration_exceeds_discord_timestamp(seconds, now=now)
            end_time_timestamp = None if permanent else now + seconds
            discord_timestamp = format_discord_end_time(end_time_timestamp)
            duration_text = format_duration_display(seconds, period, now=now)
            # Gửi thông báo vào channel log
            log_msg = None
            log_channel = guild.get_channel(config.NHAPKHO_LOG_CHANNEL_ID)
            if log_channel:
                try:
                    log_msg = await log_channel.send(
                        view=NhapKhoNoticeView(
                            member,
                            reason,
                            duration_text=duration_text,
                            end_time_text=discord_timestamp,
                        )
                    )
                except Exception:
                    log_msg = await log_channel.send(
                        f"{member.mention} vào chuồng trong {duration_text} (ra chuồng sau {discord_timestamp}) - lý do: {reason}"
                    )

            self.add_nhapkho_member(
                member.id, reason, end_time_timestamp, saved_role_ids,
                log_message_id=log_msg.id if log_msg else None,
            )

            if permanent:
                return

            # Chờ hết thời gian
            await asyncio.sleep(seconds)

            # Xuất kho — xóa tin nhắn log, gỡ role, trả role
            member_id = member.id
            await self._delete_log_message(guild, member_id)
            member = guild.get_member(member_id)
            if member:
                await self.restore_roles(
                    guild, member, roles_to_remove=[role_nhapkho]
                )
            self.remove_nhapkho_member(member_id)
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
                    log_msg = log_channel.get_partial_message(log_msg_id)
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
            info = self.nhapkho_data.get(str(member_id), {})
            saved = info.get("saved_roles", [])
            roles_to_add = role_ids_to_roles(guild, saved)
            roles_to_remove = [
                role_nhapkho
            ] if role_nhapkho and role_nhapkho in member.roles else []
            try:
                await apply_role_update(
                    member,
                    roles_to_add=roles_to_add,
                    roles_to_remove=roles_to_remove,
                    reason="Nhap kho expired",
                )
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
            end_timestamp = info.get("end_timestamp")
            remaining = None if end_timestamp is None else end_timestamp - now
            member = guild.get_member(member_id)

            if end_timestamp is None:
                if member:
                    role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
                    if role_nhapkho and role_nhapkho not in member.roles:
                        try:
                            await apply_role_update(
                                member,
                                roles_to_add=[role_nhapkho],
                                reason="Nhap kho permanent resume",
                            )
                        except Exception:
                            pass
                continue

            if remaining <= 0:
                # Hết hạn — xóa log, gỡ role nhập kho & trả role
                await self._delete_log_message(guild, member_id)
                if member:
                    role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
                    saved = info.get("saved_roles", [])
                    roles_to_add = role_ids_to_roles(guild, saved)
                    roles_to_remove = [
                        role_nhapkho
                    ] if role_nhapkho and role_nhapkho in member.roles else []
                    try:
                        await apply_role_update(
                            member,
                            roles_to_add=roles_to_add,
                            roles_to_remove=roles_to_remove,
                            reason="Nhap kho expired",
                        )
                    except Exception:
                        pass
                self.remove_nhapkho_member(member_id)
            else:
                # Còn hạn — đảm bảo role và resume timer
                if member:
                    role_nhapkho = guild.get_role(config.NHAPKHO_ROLE_ID)
                    if role_nhapkho and role_nhapkho not in member.roles:
                        try:
                            await apply_role_update(
                                member,
                                roles_to_add=[role_nhapkho],
                                reason="Nhap kho resume",
                            )
                        except Exception:
                            pass
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
        end_timestamp = info.get("end_timestamp")
        remaining = None if end_timestamp is None else end_timestamp - now

        if end_timestamp is not None and remaining <= 0:
            self.remove_nhapkho_member(member.id)
            return

        removable_role_ids = roles_to_remove_ids()
        roles_to_remove = [r for r in member.roles if r.id in removable_role_ids]
        if role_nhapkho or roles_to_remove:
            try:
                await apply_role_update(
                    member,
                    roles_to_add=[role_nhapkho] if role_nhapkho else [],
                    roles_to_remove=roles_to_remove,
                    reason="Rejoin - vẫn đang nhập kho",
                )
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
        duration_text = format_duration_display(seconds, period)
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
                self.perform_nhapkho(interaction, m, seconds, period, reason)
            )
            msg.append(
                f"{m.mention} đã bị gửi vào vườn thú."
            )

        await interaction.followup.send(
            view=NhapKhoCommandResultView(
                msg,
                duration_text=duration_text,
                reason=reason,
            )
        )

# ── Setup function (required for cog loading) ───────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(NhapKhoCog(bot))
