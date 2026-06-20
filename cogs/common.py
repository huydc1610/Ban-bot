import re
from collections.abc import Iterable

import discord

import config

TIME_RE = re.compile(r"(\d+)([dhms])")
MENTION_RE = re.compile(r"<@!?(\d+)>")
MONKEY_SPLIT_RE = re.compile(r"[,\s]+")


def has_allowed_role(interaction: discord.Interaction) -> bool:
    return any(role.id in config.ALLOWED_ROLE_ID_SET for role in interaction.user.roles)


def convert_time(time_str: str) -> int:
    time_str = time_str.lower().replace(" ", "")
    total_seconds = 0
    matches = TIME_RE.findall(time_str)
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
    seen_ids = set()
    for part in MONKEY_SPLIT_RE.split(monkeys.strip()):
        if not part:
            continue
        match = MENTION_RE.fullmatch(part)
        member_id = (
            int(match.group(1)) if match else (int(part) if part.isdigit() else None)
        )
        if member_id is None or member_id in seen_ids:
            continue

        member = guild.get_member(member_id)
        if member:
            seen_ids.add(member_id)
            members.append(member)
    return members


def role_ids_to_roles(
    guild: discord.Guild, role_ids: Iterable[int]
) -> list[discord.Role]:
    roles = []
    for role_id in role_ids:
        role = guild.get_role(int(role_id))
        if role:
            roles.append(role)
    return roles


def effective_top_role(member: discord.Member) -> discord.Role:
    for role in reversed(member.roles):
        if role.id not in config.IGNORED_BANNED_ROLE_ID_SET:
            return role
    return member.roles[0]


async def apply_role_update(
    member: discord.Member,
    *,
    roles_to_add: Iterable[discord.Role] = (),
    roles_to_remove: Iterable[discord.Role] = (),
    reason: str | None = None,
) -> bool:
    remove_ids = {role.id for role in roles_to_remove if role}
    current_roles = [role for role in member.roles if role != member.guild.default_role]

    next_roles = []
    next_ids = set()
    for role in current_roles:
        if role.id in remove_ids or role.id in next_ids:
            continue
        next_roles.append(role)
        next_ids.add(role.id)

    for role in roles_to_add:
        if role and role.id not in next_ids:
            next_roles.append(role)
            next_ids.add(role.id)

    if next_ids == {role.id for role in current_roles}:
        return False

    await member.edit(roles=next_roles, reason=reason)
    return True
