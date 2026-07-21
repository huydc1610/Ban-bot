import discord
from discord.ext import commands

import config
from cogs.common import autoban_ignored_role_ids

AUTOBAN_REASON = "Thí sinh Mr Beast tiềm năng"
AUTOBAN_NOTICE_REASON = "Do quảng cáo lừa đảo bạn sẽ nằm ở đây cho đến khi nào mod thả bạn."


def watch_channel_id() -> int:
    return int(getattr(config, "AUTOBAN_CHANNEL_ID", 0) or 0)


def delete_history_limit() -> int | None:
    value = getattr(config, "AUTOBAN_DELETE_HISTORY_LIMIT", None)
    if isinstance(value, str):
        value = value.strip()
        if value.lower() in ("", "0", "none", "all"):
            return None
    if value in (None, 0):
        return None
    return int(value)


def is_watch_channel_message(message: discord.Message, configured_channel_id: int) -> bool:
    return bool(
        configured_channel_id
        and getattr(message, "guild", None)
        and getattr(getattr(message, "channel", None), "id", None)
        == configured_channel_id
    )


def is_ignored_member(member: discord.Member, ignored_role_ids: frozenset[int]) -> bool:
    if getattr(member, "bot", False):
        return True
    return any(role.id in ignored_role_ids for role in getattr(member, "roles", ()))


def iter_cleanup_channels(
    guild: discord.Guild,
    configured_channel_id: int,
    extra_channels=(),
):
    seen_channel_ids = {configured_channel_id}
    for channel in getattr(guild, "text_channels", ()):
        channel_id = getattr(channel, "id", None)
        if channel_id not in seen_channel_ids:
            seen_channel_ids.add(channel_id)
            yield channel
    for thread in getattr(guild, "threads", ()):
        thread_id = getattr(thread, "id", None)
        if thread_id not in seen_channel_ids:
            seen_channel_ids.add(thread_id)
            yield thread
    for channel in extra_channels or ():
        channel_id = getattr(channel, "id", None)
        if channel_id not in seen_channel_ids:
            seen_channel_ids.add(channel_id)
            yield channel


def is_message_from_member(message: discord.Message, member_id: int) -> bool:
    return getattr(getattr(message, "author", None), "id", None) == member_id


class AutobanCog(commands.Cog):
    """Honeypot cog: nhắn vào kênh bẫy là ra đảo vĩnh viễn."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.processing_member_ids: set[int] = set()

    @commands.Cog.listener()
    async def on_ready(self):
        configured_channel_id = watch_channel_id()
        if configured_channel_id:
            print(f"[AutobanCog] Loaded — đang theo dõi channel {configured_channel_id}.")
        else:
            print("[AutobanCog] Loaded — chưa cấu hình AUTOBAN_CHANNEL_ID.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        configured_channel_id = watch_channel_id()
        if not is_watch_channel_message(message, configured_channel_id):
            return

        member = getattr(message, "author", None)
        if not member or not hasattr(member, "roles"):
            return
        if is_ignored_member(member, autoban_ignored_role_ids()):
            return
        if member.id in self.processing_member_ids:
            return

        self.processing_member_ids.add(member.id)
        try:
            print(
                f"[AutobanCog] Trigger autoban member {member.id} "
                f"từ channel {configured_channel_id}."
            )
            island_channel = await self.radao_member(message.guild, member)
            await self.delete_member_messages_elsewhere(
                message.guild,
                member.id,
                configured_channel_id,
                extra_channels=[island_channel] if island_channel else (),
            )
        finally:
            self.processing_member_ids.discard(member.id)

    async def radao_member(self, guild: discord.Guild, member: discord.Member):
        radao_cog = self.bot.get_cog("RadaoCog")
        if not radao_cog or not hasattr(radao_cog, "perform_permanent_radao"):
            print("[AutobanCog] Không tìm thấy RadaoCog để xử lý autoban.")
            return
        info = getattr(radao_cog, "radao_data", {}).get(str(member.id), {})
        if info.get("end_timestamp") is None and info.get("permanent"):
            return radao_cog.find_radao_channel(guild, member.id)
        return await radao_cog.perform_permanent_radao(
            guild,
            member,
            AUTOBAN_REASON,
            notice_reason=AUTOBAN_NOTICE_REASON,
        )

    async def delete_member_messages_elsewhere(
        self,
        guild: discord.Guild,
        member_id: int,
        configured_channel_id: int,
        extra_channels=(),
    ):
        limit = delete_history_limit()
        for channel in iter_cleanup_channels(
            guild,
            configured_channel_id,
            extra_channels=extra_channels,
        ):
            try:
                await self.delete_member_messages_in_channel(channel, member_id, limit)
            except (discord.Forbidden, discord.HTTPException) as e:
                print(
                    f"[AutobanCog] Không xóa được tin nhắn ở "
                    f"{getattr(channel, 'id', 'unknown')}: {e}"
                )

    async def delete_member_messages_in_channel(
        self,
        channel,
        member_id: int,
        limit: int | None,
    ):
        check = lambda msg: is_message_from_member(msg, member_id)
        if hasattr(channel, "purge"):
            await channel.purge(
                limit=limit,
                check=check,
                bulk=False,
                reason=f"Autoban cleanup for {member_id}",
            )
            return

        if not hasattr(channel, "history"):
            return

        async for message in channel.history(limit=limit):
            if check(message):
                try:
                    await message.delete()
                except (discord.Forbidden, discord.HTTPException):
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AutobanCog(bot))
