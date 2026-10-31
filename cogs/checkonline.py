import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from cogs.common import (
    allowed_role_ids,
    allowed_user_ids,
    has_allowed_role,
    load_json_dict,
)

DATA_FILE = os.path.join(config.DATA_DIR, "member.json")

ACTION_MESSAGE = "message"
ACTION_INTERACTION = "interaction"
ACTION_COMMAND = "command"
ACTION_VOICE = "voice"
ACTION_REACTION = "reaction"
ACTION_CHANNEL_CREATE = "channel_create"
ACTION_BOT_INIT = "bot_init"
ACTION_MEMBER_JOIN = "member_join"


def load_member_data() -> dict:
    return load_json_dict(DATA_FILE)


def save_member_data(data: dict) -> None:
    os.makedirs(os.path.dirname(os.fspath(DATA_FILE)), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class CheckOnlineCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.member_data: dict = load_member_data()
        self._initialized = False
        self._save_lock = asyncio.Lock()

        interval = getattr(config, "CHECK_INACTIVE_INTERVAL_HOURS", 1)
        self.check_inactive_loop.change_interval(hours=max(1, interval))
        self.check_inactive_loop.start()

    async def cog_load(self):
        asyncio.create_task(self.init_members())

    def cog_unload(self):
        self.check_inactive_loop.cancel()
        save_member_data(self.member_data)

    async def init_members(self):
        await self.bot.wait_until_ready()
        guild_id = (
            config.MAIN_GUILD_ID.id
            if isinstance(config.MAIN_GUILD_ID, discord.Object)
            else config.MAIN_GUILD_ID
        )
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        now = int(time.time())
        updated = False
        for member in guild.members:
            if member.bot:
                continue
            uid = str(member.id)
            if uid not in self.member_data:
                self.member_data[uid] = {
                    "name": str(member),
                    "last_active": now,
                    "last_action": ACTION_BOT_INIT,
                    "has_inactive_role": False,
                }
                updated = True

        if updated:
            save_member_data(self.member_data)
        self._initialized = True
        print(f"[CheckOnline] Đã khởi tạo theo dõi cho {len(self.member_data)} thành viên.")

    async def record_activity(self, member: discord.Member, action: str):
        if member.bot or not member.guild:
            return

        now = int(time.time())
        uid = str(member.id)
        user_data = self.member_data.get(uid, {})
        prev_active = user_data.get("last_active", 0)

        user_data["name"] = str(member)
        user_data["last_active"] = now
        user_data["last_action"] = action

        inactive_role_id = getattr(config, "INACTIVE_ROLE_ID", 0)
        role_removed = False
        if inactive_role_id:
            inactive_role = member.guild.get_role(inactive_role_id)
            if inactive_role and inactive_role in member.roles:
                try:
                    await member.remove_roles(
                        inactive_role, reason=f"CheckOnline: Hoạt động trở lại qua {action}"
                    )
                    role_removed = True
                    user_data["has_inactive_role"] = False
                    print(
                        f"[CheckOnline] Đã gỡ role inactive cho {member.name} ({member.id}) do tương tác: {action}"
                    )
                except discord.Forbidden:
                    print(
                        f"[CheckOnline] Không đủ quyền gỡ role inactive cho {member.name} ({member.id})"
                    )
                except Exception as e:
                    print(
                        f"[CheckOnline] Lỗi khi gỡ role inactive cho {member.name} ({member.id}): {e}"
                    )
            else:
                user_data["has_inactive_role"] = False
        else:
            user_data["has_inactive_role"] = False

        self.member_data[uid] = user_data

        if role_removed or (now - prev_active) >= 60:
            save_member_data(self.member_data)

    async def scan_and_update_members(self, guild: discord.Guild) -> dict:
        now = int(time.time())
        inactive_role_id = getattr(config, "INACTIVE_ROLE_ID", 0)
        inactive_days = getattr(config, "INACTIVE_DAYS", 7)
        threshold_seconds = inactive_days * 86400
        inactive_role = guild.get_role(inactive_role_id) if inactive_role_id else None

        admin_role_ids = allowed_role_ids()
        admin_user_ids = allowed_user_ids()

        stats = {
            "total_members": 0,
            "exempt_count": 0,
            "active_count": 0,
            "marked_inactive": 0,
            "already_inactive": 0,
            "role_assigned_errors": 0,
        }

        for member in guild.members:
            if member.bot:
                continue

            stats["total_members"] += 1

            if (
                member.id == guild.owner_id
                or member.id in admin_user_ids
                or any(r.id in admin_role_ids for r in member.roles)
            ):
                stats["exempt_count"] += 1
                continue

            uid = str(member.id)
            user_data = self.member_data.get(uid)

            if not user_data:
                self.member_data[uid] = {
                    "name": str(member),
                    "last_active": now,
                    "last_action": ACTION_BOT_INIT,
                    "has_inactive_role": False,
                }
                stats["active_count"] += 1
                continue

            last_active = user_data.get("last_active", now)
            elapsed = now - last_active

            if elapsed > threshold_seconds:
                if inactive_role:
                    if inactive_role in member.roles:
                        stats["already_inactive"] += 1
                        user_data["has_inactive_role"] = True
                    else:
                        try:
                            await member.add_roles(
                                inactive_role,
                                reason=f"CheckOnline: Không tương tác quá {inactive_days} ngày",
                            )
                            user_data["has_inactive_role"] = True
                            stats["marked_inactive"] += 1
                        except discord.Forbidden:
                            stats["role_assigned_errors"] += 1
                            print(
                                f"[CheckOnline] Không đủ quyền gán role cho {member.name} ({member.id})"
                            )
                        except Exception as e:
                            stats["role_assigned_errors"] += 1
                            print(
                                f"[CheckOnline] Lỗi gán role cho {member.name} ({member.id}): {e}"
                            )
                else:
                    stats["already_inactive"] += 1
            else:
                stats["active_count"] += 1

        save_member_data(self.member_data)
        return stats

    @tasks.loop(hours=1)
    async def check_inactive_loop(self):
        await self.bot.wait_until_ready()
        if not self._initialized:
            await self.init_members()

        inactive_role_id = getattr(config, "INACTIVE_ROLE_ID", 0)
        if not inactive_role_id:
            return

        guild_id = (
            config.MAIN_GUILD_ID.id
            if isinstance(config.MAIN_GUILD_ID, discord.Object)
            else config.MAIN_GUILD_ID
        )
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        print("[CheckOnline] Bắt đầu quét kiểm tra thành viên không hoạt động định kỳ...")
        stats = await self.scan_and_update_members(guild)
        print(
            f"[CheckOnline] Hoàn tất quét: {stats['marked_inactive']} người mới bị gán role inactive, "
            f"{stats['already_inactive']} đã có role từ trước, {stats['active_count']} đang hoạt động."
        )

    @check_inactive_loop.before_loop
    async def before_check_inactive_loop(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if isinstance(message.author, discord.Member):
            await self.record_activity(message.author, ACTION_MESSAGE)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.user or interaction.user.bot:
            return
        if isinstance(interaction.user, discord.Member):
            await self.record_activity(interaction.user, ACTION_INTERACTION)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        if not ctx.guild or not ctx.author or ctx.author.bot:
            return
        if isinstance(ctx.author, discord.Member):
            await self.record_activity(ctx.author, ACTION_COMMAND)

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        if not interaction.guild or not interaction.user or interaction.user.bot:
            return
        if isinstance(interaction.user, discord.Member):
            await self.record_activity(interaction.user, ACTION_COMMAND)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        if not guild:
            return
        await asyncio.sleep(1.0)
        try:
            async for entry in guild.audit_logs(
                limit=3, action=discord.AuditLogAction.channel_create
            ):
                if getattr(getattr(entry, "target", None), "id", None) == channel.id:
                    actor = entry.user
                    if isinstance(actor, discord.Member) and not actor.bot:
                        await self.record_activity(actor, ACTION_CHANNEL_CREATE)
                    break
        except Exception as e:
            print(f"[CheckOnline] Không thể kiểm tra audit log tạo kênh: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        if member.bot:
            return
        if before.channel != after.channel and after.channel is not None:
            await self.record_activity(member, ACTION_VOICE)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member and not payload.member.bot:
            await self.record_activity(payload.member, ACTION_REACTION)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        await self.record_activity(member, ACTION_MEMBER_JOIN)

    @app_commands.command(
        name="checkonline_scan",
        description="Quét toàn bộ server và gán role cho các thành viên không hoạt động.",
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    async def checkonline_scan(self, interaction: discord.Interaction):
        if not has_allowed_role(interaction):
            return await interaction.response.send_message(
                "Bạn không có quyền dùng lệnh này.", ephemeral=True
            )

        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message(
                "Lệnh này chỉ có thể sử dụng trong server.", ephemeral=True
            )

        inactive_role_id = getattr(config, "INACTIVE_ROLE_ID", 0)
        if not inactive_role_id or not guild.get_role(inactive_role_id):
            return await interaction.response.send_message(
                "⚠️ Chưa cấu hình `INACTIVE_ROLE_ID` hoặc không tìm thấy role trong server! Hãy kiểm tra file `config.py`.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=False, thinking=True)
        stats = await self.scan_and_update_members(guild)

        embed = discord.Embed(
            title="📊 KẾT QUẢ QUÉT CHECK ONLINE",
            description=f"Đã hoàn thành kiểm tra theo mốc **{getattr(config, 'INACTIVE_DAYS', 7)} ngày**.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="👥 Tổng thành viên quét", value=f"`{stats['total_members']}`", inline=True
        )
        embed.add_field(
            name="🛡️ Miễn trừ (Admin / Owner)",
            value=f"`{stats['exempt_count']}`",
            inline=True,
        )
        embed.add_field(
            name="🟢 Đang hoạt động", value=f"`{stats['active_count']}`", inline=True
        )
        embed.add_field(
            name="⚠️ Mới gán role Inactive",
            value=f"`{stats['marked_inactive']}`",
            inline=True,
        )
        embed.add_field(
            name="💤 Đã mang role Inactive từ trước",
            value=f"`{stats['already_inactive']}`",
            inline=True,
        )
        if stats["role_assigned_errors"] > 0:
            embed.add_field(
                name="❌ Lỗi phân quyền",
                value=f"`{stats['role_assigned_errors']}`",
                inline=True,
            )
        embed.timestamp = datetime.now(timezone.utc)

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="checkonline_status",
        description="Kiểm tra thời gian và hành động gần nhất của một thành viên.",
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    @app_commands.describe(member="Thành viên cần kiểm tra (để trống nếu kiểm tra bản thân)")
    async def checkonline_status(
        self, interaction: discord.Interaction, member: discord.Member | None = None
    ):
        target = member or interaction.user
        if not isinstance(target, discord.Member):
            return await interaction.response.send_message(
                "Không tìm thấy thông tin thành viên.", ephemeral=True
            )

        uid = str(target.id)
        user_data = self.member_data.get(uid)

        inactive_role_id = getattr(config, "INACTIVE_ROLE_ID", 0)
        has_role = False
        if inactive_role_id and target.guild:
            role = target.guild.get_role(inactive_role_id)
            has_role = bool(role and role in target.roles)

        action_labels = {
            ACTION_MESSAGE: "Gửi tin nhắn (Chat)",
            ACTION_INTERACTION: "Tương tác (Nút bấm / Menu / Bot)",
            ACTION_COMMAND: "Sử dụng lệnh Bot",
            ACTION_VOICE: "Tham gia Voice",
            ACTION_REACTION: "Thả cảm xúc (Reaction)",
            ACTION_CHANNEL_CREATE: "Tạo kênh mới",
            ACTION_BOT_INIT: "Khởi tạo hệ thống (Ân hạn)",
            ACTION_MEMBER_JOIN: "Tham gia server",
        }

        embed = discord.Embed(
            title=f"🔍 HOẠT ĐỘNG: {target.display_name}",
            color=discord.Color.red() if has_role else discord.Color.green(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name="Tài khoản", value=f"{target.mention} (`{target.id}`)", inline=False
        )

        if user_data:
            last_active = user_data.get("last_active")
            last_action = user_data.get("last_action", "Không rõ")
            action_desc = action_labels.get(last_action, last_action)

            embed.add_field(
                name="Lần cuối hoạt động",
                value=f"<t:{last_active}:R> (<t:{last_active}:F>)",
                inline=False,
            )
            embed.add_field(name="Hành động gần nhất", value=action_desc, inline=True)
        else:
            embed.add_field(
                name="Lần cuối hoạt động",
                value="*Chưa có dữ liệu ghi nhận*",
                inline=False,
            )

        status_text = (
            "⚠️ Đang mang role Inactive" if has_role else "🟢 Bình thường / Đang hoạt động"
        )
        embed.add_field(name="Trạng thái", value=status_text, inline=True)
        embed.timestamp = datetime.now(timezone.utc)

        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(CheckOnlineCog(bot))
