import json
import os
import re
import time
from collections.abc import Iterable

import discord

import config

TIME_RE = re.compile(r"(\d+)([dhms])")
MENTION_RE = re.compile(r"<@!?(\d+)>")
MONKEY_SPLIT_RE = re.compile(r"[,\s]+")
MAX_DISCORD_UNIX_TIMESTAMP = 253402300799
INFINITE_TIME_TEXT = "infinity"


def duration_exceeds_discord_timestamp(
    seconds: int | None,
    *,
    now: int | None = None,
) -> bool:
    if seconds is None:
        return True
    if now is None:
        now = int(time.time())
    return now + seconds > MAX_DISCORD_UNIX_TIMESTAMP


def format_duration_display(
    seconds: int | None,
    period: str | None,
    *,
    now: int | None = None,
) -> str:
    if duration_exceeds_discord_timestamp(seconds, now=now):
        return INFINITE_TIME_TEXT
    return period or INFINITE_TIME_TEXT


def format_discord_end_time(
    end_timestamp: int | None,
    *,
    include_full: bool = False,
) -> str:
    if end_timestamp is None or end_timestamp > MAX_DISCORD_UNIX_TIMESTAMP:
        return INFINITE_TIME_TEXT
    if include_full:
        return f"<t:{end_timestamp}:R> (<t:{end_timestamp}:F>)"
    return f"<t:{end_timestamp}:R>"


def config_id_set(
    set_name: str,
    list_name: str,
    default: Iterable[int] = (),
) -> frozenset[int]:
    values = getattr(config, set_name, None)
    if values is None:
        values = getattr(config, list_name, default)
    return frozenset(int(value) for value in values)


def allowed_role_ids() -> frozenset[int]:
    return config_id_set("ALLOWED_ROLE_ID_SET", "ALLOWED_ROLE_IDS")


def allowed_user_ids() -> frozenset[int]:
    return config_id_set("ALLOWED_USER_ID_SET", "ALLOWED_USER_IDS")


def command_blocked_role_ids() -> frozenset[int]:
    default = (
        getattr(config, "TARGET_ROLE_ID", 0),
        getattr(config, "NHAPKHO_ROLE_ID", 0),
    )
    return config_id_set(
        "COMMAND_BLOCKED_ROLE_ID_SET",
        "COMMAND_BLOCKED_ROLE_IDS",
        default,
    )


def roles_to_remove_ids() -> frozenset[int]:
    return config_id_set("ROLES_TO_REMOVE_ID_SET", "ROLES_TO_REMOVE")


def ignored_banned_role_ids() -> frozenset[int]:
    return config_id_set("IGNORED_BANNED_ROLE_ID_SET", "IGNORED_BANNED_ROLES")


def ignored_banned_user_ids() -> frozenset[int]:
    return config_id_set("IGNORED_BANNED_USER_ID_SET", "IGNORED_BANNED_USERS")


def autoban_ignored_role_ids() -> frozenset[int]:
    return config_id_set("AUTOBAN_IGNORED_ROLE_ID_SET", "AUTOBAN_IGNORED_ROLE_IDS")


def load_json_dict(path: str | os.PathLike) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_json_dict(path: str | os.PathLike, data: dict):
    os.makedirs(os.path.dirname(os.fspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def has_allowed_role(interaction: discord.Interaction) -> bool:
    if is_guild_owner(interaction):
        return True

    roles = getattr(interaction.user, "roles", ())
    blocked_role_ids = command_blocked_role_ids()
    if any(role.id in blocked_role_ids for role in roles):
        return False

    user_id = getattr(interaction.user, "id", None)
    if user_id in allowed_user_ids():
        return True

    return any(role.id in allowed_role_ids() for role in roles)


def is_guild_owner(interaction: discord.Interaction) -> bool:
    guild = getattr(interaction, "guild", None)
    owner_id = getattr(guild, "owner_id", None)
    return owner_id is not None and owner_id == getattr(interaction.user, "id", None)


def shares_allowed_role(
    first_member: discord.Member,
    second_member: discord.Member,
) -> bool:
    allowed_ids = allowed_role_ids()
    first_role_ids = {role.id for role in getattr(first_member, "roles", ())}
    second_role_ids = {role.id for role in getattr(second_member, "roles", ())}
    return bool(allowed_ids & first_role_ids & second_role_ids)


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
    if getattr(member, "id", None) in ignored_banned_user_ids():
        return member.roles[0]
    ignored_role_ids = ignored_banned_role_ids()
    for role in reversed(member.roles):
        if role.id not in ignored_role_ids:
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
