import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import time

import config
from cogs.common import (
    allowed_role_ids,
    allowed_user_ids,
    apply_role_update,
    convert_time,
    duration_exceeds_discord_timestamp,
    effective_top_role,
    format_discord_end_time,
    format_duration_display,
    has_allowed_role,
    is_guild_owner,
    load_json_dict,
    parse_monkeys,
    role_ids_to_roles,
    roles_to_remove_ids,
    save_json_dict,
    shares_allowed_role,
)

DATA_FILE = os.path.join(config.DATA_DIR, "radao_data.json")
RADAO_EXPIRE_ACTION_BAN = "ban"
AUTOBAN_EXPIRED_BAN_REASON = "Autoban: không được gỡ radao sau 1 tuần"


class RadaoNoticeView(discord.ui.LayoutView):
    PANEL_TITLE = "# ĐẢO KHỈ | MONKEY ISLAND\n"

    def __init__(
        self,
        member: discord.Member,
        reason: str,
        *,
        end_timestamp: int | None = None,
        notice_reason: str | None = None,
    ):
        super().__init__(timeout=None)

        permanent = end_timestamp is None
        if permanent:
            time_text = format_discord_end_time(end_timestamp, include_full=True)
        else:
            end_time_text = format_discord_end_time(end_timestamp, include_full=True)
            time_text = (
                end_time_text
                if end_time_text == "infinity"
                else f"Kick sau {end_time_text}."
            )
        display_reason = notice_reason or reason

        panel_text = (
            "### 👤 ĐỐI TƯỢNG\n"
            f"> {member.mention}\n"
            "### ⏳ ĐẾM NGƯỢC\n"
            f"> **{time_text}**\n"
            "### 📝 LÝ DO\n"
            f"> **{display_reason}**\n"
        )

        items = [
            discord.ui.TextDisplay(self.PANEL_TITLE),
            discord.ui.Separator(),
            discord.ui.TextDisplay(panel_text),
        ]

        items.extend([
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"-# Update <t:{int(time.time())}:f>"),
        ])

        container = discord.ui.Container(*items)
        self.add_item(container)


class RadaoCommandResultView(discord.ui.LayoutView):
    def __init__(
        self,
        result_lines: list[str],
        *,
        duration_text: str,
        reason: str,
        reason_lines: list[str] | None = None,
    ):
        super().__init__(timeout=None)

        result_text = "\n".join(f"> {line}" for line in result_lines)
        if not result_text:
            result_text = "> Không có đối tượng nào được xử lý."
        reason_entries = [reason, *(reason_lines or [])]
        reason_text = "\n".join(f"> **{line}**" for line in reason_entries)
        panel_text = (
            "### 👤 ĐỐI TƯỢNG\n"
            f"{result_text}\n"
            "### ⏳ THỜI GIAN\n"
            f"> **{duration_text}**\n"
            "### 📝 LÝ DO\n"
            f"{reason_text}\n"
        )
        items = [
            discord.ui.TextDisplay(panel_text),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"-# Update <t:{int(time.time())}:f>"),
        ]

        container = discord.ui.Container(*items)
        self.add_item(container)


class BanCommandResultView(discord.ui.LayoutView):
    def __init__(
        self,
        user: discord.Member,
        *,
        status: str = "Đã ban khỏi server.",
        reason: str | None = None,
    ):
        super().__init__(timeout=None)

        reason_text = ""
        if reason:
            reason_text = (
                "### 📝 LÝ DO\n"
                f"> **{reason}**\n"
            )
        panel_text = (
            "### 👤 ĐỐI TƯỢNG\n"
            f"> {user.mention}\n"
            "### ‼️ TRẠNG THÁI\n"
            f"> **{status}**\n"
            f"{reason_text}"
        )
        items = [
            discord.ui.TextDisplay(panel_text),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"-# Update <t:{int(time.time())}:f>"),
        ]

        container = discord.ui.Container(*items)
        self.add_item(container)


class GiaicuuCommandResultView(discord.ui.LayoutView):
    def __init__(self, result_lines: list[str]):
        super().__init__(timeout=None)

        result_text = "\n".join(f"> {line}" for line in result_lines)
        panel_text = (
            "### 🚁 ĐỘI CỨU HỘ DADEN 🏥\n"
            f"{result_text}\n"
        )
        items = [
            discord.ui.TextDisplay(panel_text),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"-# Update <t:{int(time.time())}:f>"),
        ]

        container = discord.ui.Container(*items)
        self.add_item(container)


# ── Data helpers ─────────────────────────────────────────────────────
def load_radao_data() -> dict:
    return load_json_dict(DATA_FILE)


def save_radao_data(data: dict):
    save_json_dict(DATA_FILE, data)


# ── Cog ──────────────────────────────────────────────────────────────
class RadaoCog(commands.Cog):
    """Cog quản lý lệnh /radao và /giaicuu (cho khỉ ra đảo hoặc giải cứu)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.radao_data: dict = load_radao_data()
        self.temp_saved_roles: dict[int, list[int]] = {}

    # ── Data management ──────────────────────────────────────────────
    def add_radao_member(
        self,
        member_id: int,
        reason: str,
        end_timestamp: int | None,
        saved_roles: list[int],
        expire_action: str | None = None,
    ):
        data = {
            "reason": reason,
            "end_timestamp": end_timestamp,
            "saved_roles": saved_roles,
            "permanent": end_timestamp is None,
        }
        if expire_action:
            data["expire_action"] = expire_action
        self.radao_data[str(member_id)] = data
        save_radao_data(self.radao_data)

    def remove_radao_member(self, member_id: int):
        if str(member_id) in self.radao_data:
            del self.radao_data[str(member_id)]
            save_radao_data(self.radao_data)

    async def delete_radao_channel(self, guild: discord.Guild, member_id: int):
        channel = self.find_radao_channel(guild, member_id)
        if not channel:
            return
        try:
            await channel.delete()
        except Exception:
            pass

    async def ban_expired_radao_member(self, guild: discord.Guild, member_id: int) -> bool:
        member = guild.get_member(member_id)
        target = member or discord.Object(id=member_id)
        try:
            await guild.ban(target, reason=AUTOBAN_EXPIRED_BAN_REASON)
        except discord.Forbidden as e:
            print(f"[RadaoCog] Không đủ quyền ban autoban member {member_id}: {e}")
            return False
        except discord.HTTPException as e:
            print(f"[RadaoCog] Discord API lỗi khi ban autoban member {member_id}: {e}")
            return False

        await self.delete_radao_channel(guild, member_id)
        self.temp_saved_roles.pop(member_id, None)
        self.remove_radao_member(member_id)
        return True

    async def handle_expired_radao(
        self,
        guild: discord.Guild,
        member_id: int,
        info: dict | None = None,
    ):
        info = info or self.radao_data.get(str(member_id), {})
        if not info:
            return

        if info.get("expire_action") == RADAO_EXPIRE_ACTION_BAN:
            await self.ban_expired_radao_member(guild, member_id)
            return

        member = guild.get_member(member_id)
        if member:
            role_radao = guild.get_role(config.TARGET_ROLE_ID)
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
            await self.delete_radao_channel(guild, member_id)
        self.remove_radao_member(member_id)

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

    async def release_member(self, guild: discord.Guild, member: discord.Member) -> bool:
        role_radao = guild.get_role(config.TARGET_ROLE_ID)
        if not role_radao or role_radao not in member.roles:
            return False

        await self.restore_roles(guild, member, roles_to_remove=[role_radao])
        self.remove_radao_member(member.id)

        category = guild.get_channel(config.TARGET_CATEGORY_ID)
        if category:
            for channel in category.text_channels:
                if str(member.id) in (channel.topic or "") or str(member.id) in channel.name:
                    await channel.delete()

        return True

    async def rescue_member(self, guild: discord.Guild, member: discord.Member) -> tuple[bool, bool]:
        radao_released = await self.release_member(guild, member)

        nhapkho_cog = self.bot.get_cog("NhapKhoCog")
        if nhapkho_cog is None:
            return radao_released, False

        nhapkho_released = await nhapkho_cog.release_member(guild, member)
        return radao_released, nhapkho_released

    # ── Core radao logic ─────────────────────────────────────────────
    async def perform_radao(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        seconds: int,
        period: str,
        reason: str,
    ):
        return await self.perform_radao_for_member(
            interaction.guild,
            member,
            seconds,
            period,
            reason,
            moderator=interaction.user,
        )

    async def perform_permanent_radao(
        self,
        guild: discord.Guild,
        member: discord.Member,
        reason: str,
        *,
        notice_reason: str | None = None,
    ):
        return await self.perform_radao_for_member(
            guild,
            member,
            None,
            None,
            reason,
            notice_reason=notice_reason,
        )

    async def perform_autoban_radao(
        self,
        guild: discord.Guild,
        member: discord.Member,
        seconds: int,
        reason: str,
        *,
        notice_reason: str | None = None,
    ):
        return await self.perform_radao_for_member(
            guild,
            member,
            seconds,
            "7d",
            reason,
            notice_reason=notice_reason,
            expire_action=RADAO_EXPIRE_ACTION_BAN,
        )

    def find_radao_channel(self, guild: discord.Guild, member_id: int):
        category = guild.get_channel(config.TARGET_CATEGORY_ID)
        if not category:
            return None
        for channel in category.text_channels:
            if str(member_id) in (channel.topic or "") or str(member_id) in channel.name:
                return channel
        return None

    async def perform_radao_for_member(
        self,
        guild: discord.Guild,
        member: discord.Member,
        seconds: int | None,
        period: str | None,
        reason: str,
        *,
        notice_reason: str | None = None,
        expire_action: str | None = None,
        moderator: discord.Member | None = None,
    ):
        now = int(time.time())
        permanent = duration_exceeds_discord_timestamp(seconds, now=now)
        role_radao = guild.get_role(config.TARGET_ROLE_ID)
        category = guild.get_channel(config.TARGET_CATEGORY_ID)

        if not role_radao or not category:
            return None

        removable_role_ids = roles_to_remove_ids()
        roles_to_remove = [r for r in member.roles if r.id in removable_role_ids]
        existing_info = self.radao_data.get(str(member.id), {})
        saved_role_ids = existing_info.get("saved_roles") or [
            r.id for r in roles_to_remove
        ]
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

            end_time_timestamp = None if permanent else now + seconds

            self.add_radao_member(
                member.id,
                reason,
                end_time_timestamp,
                saved_role_ids,
                expire_action=expire_action,
            )

            channel = self.find_radao_channel(guild, member.id)
            private_channel = moderator is not None or expire_action == RADAO_EXPIRE_ACTION_BAN
            if private_channel:
                # /radao và autoban dùng quyền riêng, không kế thừa quyền mở từ category.
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False,
                    ),
                }
                participants = [member, guild.me]
                if moderator is not None:
                    participants.append(moderator)
                participants.extend(
                    role for role_id in allowed_role_ids()
                    if (role := guild.get_role(role_id)) is not None
                )
                participants.extend(
                    guild.get_member(user_id) or discord.Object(id=user_id)
                    for user_id in allowed_user_ids()
                )
                for participant in participants:
                    overwrites[participant] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                    )
            elif not channel:
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

            if not channel:
                channel_prefix = "ban-scamer" if expire_action == RADAO_EXPIRE_ACTION_BAN else "dao-khi"
                channel = await guild.create_text_channel(
                    name=f"{channel_prefix}-{member.display_name}",
                    category=category,
                    topic=f"ID: {member.id} | Ra đảo vì: {reason}",
                    overwrites=overwrites,
                )
            elif private_channel:
                await channel.edit(overwrites=overwrites, reason=reason)

            try:
                notice_view = RadaoNoticeView(
                    member,
                    reason,
                    end_timestamp=end_time_timestamp,
                    notice_reason=notice_reason,
                )
                await channel.send(view=notice_view)
            except Exception:
                if permanent:
                    await channel.send(
                        "\n".join(
                            [
                                f"Chào mừng {member.mention} đến với đảo. Bạn sẽ nằm ở đây cho đến khi nào mod thả bạn.",
                                f"Lý do ra đảo: **{reason}**",
                            ]
                        )
                    )
                else:
                    discord_timestamp = f"<t:{end_time_timestamp}:R>"
                    full_date_timestamp = f"<t:{end_time_timestamp}:F>"
                    await channel.send(
                        "\n".join(
                            [
                                f"Chào mừng {member.mention} đến với đảo! Về bờ sau {discord_timestamp} ({full_date_timestamp}).",
                                f"Lý do ra đảo: **{reason}**",
                            ]
                        )
                    )

            if permanent:
                return channel

            await asyncio.sleep(seconds)

            member_id = member.id
            current_info = self.radao_data.get(str(member_id), {})
            if current_info.get("end_timestamp") != end_time_timestamp:
                return channel

            await self.handle_expired_radao(guild, member_id, current_info)
            return channel
        except Exception as e:
            print(f"Lỗi quy trình: {e}")
            return None

    async def resume_radao_timer(
        self, guild: discord.Guild, member_id: int, remaining_seconds: int
    ):
        await asyncio.sleep(remaining_seconds)
        info = self.radao_data.get(str(member_id), {})
        if not info:
            return
        end_timestamp = info.get("end_timestamp")
        if end_timestamp is None or int(end_timestamp) > int(time.time()):
            return

        await self.handle_expired_radao(guild, member_id, info)

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
            end_timestamp = info.get("end_timestamp")
            member = guild.get_member(member_id)

            if end_timestamp is None:
                if member:
                    role_radao = guild.get_role(config.TARGET_ROLE_ID)
                    if role_radao and role_radao not in member.roles:
                        try:
                            await apply_role_update(
                                member,
                                roles_to_add=[role_radao],
                                reason="Radao permanent resume",
                            )
                        except Exception:
                            pass
                continue

            remaining = int(end_timestamp) - now
            if remaining <= 0:
                await self.handle_expired_radao(guild, member_id, info)
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
        end_timestamp = info.get("end_timestamp")

        if end_timestamp is not None:
            now = int(time.time())
            remaining = int(end_timestamp) - now
            if remaining <= 0:
                await self.handle_expired_radao(guild, member.id, info)
                return

        removable_role_ids = roles_to_remove_ids()
        roles_to_remove = [r for r in member.roles if r.id in removable_role_ids]
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

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        await self.delete_radao_channel(guild, user.id)

        self.temp_saved_roles.pop(user.id, None)
        self.remove_radao_member(user.id)

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
        reason_notes = []
        duration_text = format_duration_display(seconds, period)
        for m in targets:
            if not is_guild_owner(interaction):
                if m.id == interaction.user.id:
                    if interaction.user.id != config.SELF_BAN_ALLOWED_ID:
                        msg.append("Đừng tự bắn vào chân thế chứ bro")
                        continue
                else:
                    target_top_role = effective_top_role(m)
                    if target_top_role > interaction.user.top_role:
                        reason_notes.append(
                            f"Bạn không thể timeout {m.mention} — người này có quyền cao hơn bạn."
                        )
                        continue
                    if (
                        target_top_role == interaction.user.top_role
                        and not shares_allowed_role(interaction.user, m)
                    ):
                        reason_notes.append(
                            f"Không thể timeout {m.mention} — người này có cùng role với bạn."
                        )
                        continue
            asyncio.create_task(
                self.perform_radao(interaction, m, seconds, period, reason)
            )
            msg.append(
                f"Bonk🔨 bà zà mài {m.mention} ra đảo."
            )

        await interaction.followup.send(
            view=RadaoCommandResultView(
                msg,
                duration_text=duration_text,
                reason=reason,
                reason_lines=reason_notes,
            )
        )

    @app_commands.command(
        name="ban", description="Ban khỉ khỏi server."
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    @app_commands.describe(user="Member cần ban")
    async def ban(self, interaction: discord.Interaction, user: discord.Member):
        if not has_allowed_role(interaction):
            return await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )

        await interaction.response.defer()
        try:
            await interaction.guild.ban(user, reason=f"Slash /ban bởi {interaction.user}")
        except discord.Forbidden:
            return await interaction.followup.send(
                view=BanCommandResultView(
                    user,
                    status="Không ban được.",
                    reason="Bot không đủ quyền ban người này. Hãy kiểm tra role bot và quyền Ban Members.",
                )
            )
        await interaction.followup.send(view=BanCommandResultView(user))

    @app_commands.command(
        name="giaicuu", description="Giải cứu khỉ khỏi đảo hoặc vườn thú."
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    @app_commands.describe(monkeys="Tag hoặc ID")
    async def giaicuu(self, interaction: discord.Interaction, monkeys: str):
        if not has_allowed_role(interaction):
            return await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )

        nhapkho_cog = self.bot.get_cog("NhapKhoCog")
        if nhapkho_cog is None:
            return await interaction.response.send_message(
                "Không tìm thấy cog nhập kho.", ephemeral=True
            )

        targets = parse_monkeys(interaction.guild, monkeys)
        if not targets:
            return await interaction.response.send_message(
                "Không tìm thấy ai.", ephemeral=True
            )

        await interaction.response.defer()
        msg = []
        for m in targets:
            radao_released, nhapkho_released = await self.rescue_member(
                interaction.guild, m
            )
            if radao_released and nhapkho_released:
                msg.append(f"Đã giải cứu {m.mention} khỏi đảo và vườn thú.")
            elif radao_released:
                msg.append(f"Đã đưa {m.mention} về bờ.")
            elif nhapkho_released:
                msg.append(f"{m.mention} đã được thả về tự nhiên.")
            else:
                msg.append(f"{m.mention} không bị radao hoặc nhapkho.")
        await interaction.followup.send(view=GiaicuuCommandResultView(msg))


# ── Setup function (required for cog loading) ───────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(RadaoCog(bot))
