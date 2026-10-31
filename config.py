
import os
import re
import discord
from dotenv import load_dotenv

load_dotenv(override=True)


def int_env_or_existing(name: str, default: int = 0) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def list_int_env(name: str, default: list[int] | None = None) -> list[int]:
    if default is None:
        default = []
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return list(default)
    items = re.split(r"[,;\s]+", value.strip())
    result = []
    for item in items:
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            pass
    return result


def str_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value is not None and value.strip() != "" else default


MAIN_GUILD_ID = discord.Object(
    id=int_env_or_existing("MAIN_GUILD_ID", 1513847925791391835)
)

DATA_DIR = str_env("DATA_DIR", "data")

ALLOWED_ROLE_IDS = list_int_env(
    "ALLOWED_ROLE_IDS", [1535211798397976576, 1536067056020095007]
)
ALLOWED_ROLE_ID_SET = frozenset(ALLOWED_ROLE_IDS)

ALLOWED_USER_IDS = list_int_env("ALLOWED_USER_IDS", [])
ALLOWED_USER_ID_SET = frozenset(ALLOWED_USER_IDS)

IGNORED_BANNED_ROLES = list_int_env("IGNORED_BANNED_ROLES", [])
IGNORED_BANNED_ROLE_ID_SET = frozenset(IGNORED_BANNED_ROLES)

IGNORED_BANNED_USERS = list_int_env("IGNORED_BANNED_USERS", [])
IGNORED_BANNED_USER_ID_SET = frozenset(IGNORED_BANNED_USERS)

ROLES_TO_REMOVE = list_int_env(
    "ROLES_TO_REMOVE", [1536380806296117258, 1535211798397976576]
)
ROLES_TO_REMOVE_ID_SET = frozenset(ROLES_TO_REMOVE)

SELF_BAN_ALLOWED_ID = int_env_or_existing("SELF_BAN_ALLOWED_ID", 1397455938214039723)


TARGET_ROLE_ID = int_env_or_existing("TARGET_ROLE_ID", 1536660908699287572)

TARGET_CATEGORY_ID = int_env_or_existing("TARGET_CATEGORY_ID", 1536661272488185896)


NHAPKHO_ROLE_ID = int_env_or_existing("NHAPKHO_ROLE_ID", 1536661024655286393)

NHAPKHO_LOG_CHANNEL_ID = int_env_or_existing(
    "NHAPKHO_LOG_CHANNEL_ID", 1536662211425206372
)


COMMAND_BLOCKED_ROLE_IDS = list_int_env(
    "COMMAND_BLOCKED_ROLE_IDS", [TARGET_ROLE_ID, NHAPKHO_ROLE_ID]
)
COMMAND_BLOCKED_ROLE_ID_SET = frozenset(COMMAND_BLOCKED_ROLE_IDS)


AUTOBAN_CHANNEL_ID = int_env_or_existing("AUTOBAN_CHANNEL_ID", 1536663991408132180)

AUTOBAN_IGNORED_ROLE_IDS = list_int_env("AUTOBAN_IGNORED_ROLE_IDS", list(ALLOWED_ROLE_IDS))
AUTOBAN_IGNORED_ROLE_ID_SET = frozenset(AUTOBAN_IGNORED_ROLE_IDS)

AUTOBAN_DELETE_HISTORY_LIMIT = int_env_or_existing("AUTOBAN_DELETE_HISTORY_LIMIT", 100)


AUTO_MESSAGE_ACTOR_BOT_ID = int_env_or_existing(
    "AUTO_MESSAGE_ACTOR_BOT_ID", 792081366862790687
)

AUTO_MESSAGE_ROLE_ID = int_env_or_existing(
    "AUTO_MESSAGE_ROLE_ID", 1551252815366586569
)

AUTO_MESSAGE_CHANNEL_ID = int_env_or_existing(
    "AUTO_MESSAGE_CHANNEL_ID", 1513847926735241347
)

AUTO_MESSAGE_NOTIFY_USER_ID = int_env_or_existing(
    "AUTO_MESSAGE_NOTIFY_USER_ID", 960541228422815824
)


AUTO_KICK_ROLE_ID = int_env_or_existing("AUTO_KICK_ROLE_ID", 1536347679070621696)

AUTO_KICK_DAYS = int_env_or_existing("AUTO_KICK_DAYS", 3)

CHANNEL_LOGS_BOT = int_env_or_existing("CHANNEL_LOGS_BOT", 1536097860632715374)


INACTIVE_ROLE_ID = int_env_or_existing("INACTIVE_ROLE_ID", 0)

INACTIVE_DAYS = int_env_or_existing("INACTIVE_DAYS", 7)

CHECK_INACTIVE_INTERVAL_HOURS = int_env_or_existing(
    "CHECK_INACTIVE_INTERVAL_HOURS", 1
)
