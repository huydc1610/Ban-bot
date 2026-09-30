import asyncio
from collections import deque
from datetime import timedelta

import discord
from discord.ext import commands

import config


AUDIT_RETRY_DELAYS = (0.5, 1.0, 1.5)
AUDIT_LOG_LIMIT = 10
PROCESSED_ENTRY_LIMIT = 1_000
VERIFY_EMOJI = "<a:chich_dien:1524723069476798648>"


def role_was_added(before: discord.Member, after: discord.Member, role_id: int) -> bool:
    before_role_ids = {role.id for role in getattr(before, "roles", ())}
    after_role_ids = {role.id for role in getattr(after, "roles", ())}
    return role_id not in before_role_ids and role_id in after_role_ids


def audit_entry_matches(
    entry: discord.AuditLogEntry,
    actor_id: int,
    target_id: int,
    role_id: int,
) -> bool:
    if getattr(entry, "action", None) is not discord.AuditLogAction.member_role_update:
        return False
    if getattr(getattr(entry, "user", None), "id", None) != actor_id:
        return False
    if getattr(getattr(entry, "target", None), "id", None) != target_id:
        return False
    added_roles = getattr(getattr(entry, "after", None), "roles", ())
    return any(getattr(role, "id", None) == role_id for role in added_roles)


class AutoMessageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._processed_entry_ids: set[int] = set()
        self._processed_entry_order: deque[int] = deque()
        self._dedupe_lock = asyncio.Lock()

    def _remember_entry(self, entry_id: int) -> None:
        if len(self._processed_entry_order) >= PROCESSED_ENTRY_LIMIT:
            expired_entry_id = self._processed_entry_order.popleft()
            self._processed_entry_ids.discard(expired_entry_id)
        self._processed_entry_order.append(entry_id)
        self._processed_entry_ids.add(entry_id)

    def _forget_entry(self, entry_id: int) -> None:
        self._processed_entry_ids.discard(entry_id)
        try:
            self._processed_entry_order.remove(entry_id)
        except ValueError:
            pass

    async def _claim_entry(self, entry_id: int) -> bool:
        async with self._dedupe_lock:
            if entry_id in self._processed_entry_ids:
                return False
            self._remember_entry(entry_id)
            return True

    async def _find_matching_entry(
        self,
        guild: discord.Guild,
        target_id: int,
        audit_after,
    ):
        actor_id = config.AUTO_MESSAGE_ACTOR_BOT_ID
        role_id = config.AUTO_MESSAGE_ROLE_ID
        async for entry in guild.audit_logs(
            limit=AUDIT_LOG_LIMIT,
            action=discord.AuditLogAction.member_role_update,
            user=discord.Object(id=actor_id),
            after=audit_after,
        ):
            if audit_entry_matches(entry, actor_id, target_id, role_id):
                return entry
        return None

    async def _wait_for_matching_entry(
        self,
        guild: discord.Guild,
        target_id: int,
        audit_after,
    ):
        for delay in AUDIT_RETRY_DELAYS:
            await asyncio.sleep(delay)
            try:
                entry = await self._find_matching_entry(guild, target_id, audit_after)
            except (discord.Forbidden, discord.HTTPException) as error:
                print(f"[AutoMessageCog] Không đọc được audit log: {error}")
                continue
            if entry is not None:
                return entry
        return None

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild_id = getattr(config.MAIN_GUILD_ID, "id", config.MAIN_GUILD_ID)
        if getattr(after.guild, "id", None) != guild_id:
            return

        role_id = config.AUTO_MESSAGE_ROLE_ID
        if not role_was_added(before, after, role_id):
            return

        audit_after = discord.utils.utcnow() - timedelta(seconds=2)
        entry = await self._wait_for_matching_entry(after.guild, after.id, audit_after)
        if entry is None or not await self._claim_entry(entry.id):
            return

        channel = after.guild.get_channel(config.AUTO_MESSAGE_CHANNEL_ID)
        if channel is None or not hasattr(channel, "send"):
            print(
                "[AutoMessageCog] Không tìm thấy channel thông báo "
                f"{config.AUTO_MESSAGE_CHANNEL_ID}."
            )
            self._forget_entry(entry.id)
            return

        message = (
            f"Wakeup now <@{config.AUTO_MESSAGE_NOTIFY_USER_ID}> {after.mention} "
            f"đã verify. DO YOUR JOB{VERIFY_EMOJI}"
        )
        allowed_mentions = discord.AllowedMentions(
            everyone=False,
            roles=False,
            users=[discord.Object(id=config.AUTO_MESSAGE_NOTIFY_USER_ID), after],
            replied_user=False,
        )
        try:
            await channel.send(message, allowed_mentions=allowed_mentions)
        except (discord.Forbidden, discord.HTTPException) as error:
            self._forget_entry(entry.id)
            print(f"[AutoMessageCog] Không gửi được thông báo verify: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMessageCog(bot))
