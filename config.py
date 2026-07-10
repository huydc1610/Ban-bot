"""
Config file cho Ban-bot.
Thay đổi các ID ở đây để phù hợp với server của bạn.
"""

import os
import discord


def int_env_or_existing(name: str, default: int = 0) -> int:
    value = os.getenv(name, globals().get(name, default))
    if value in (None, ""):
        value = default
    return int(value)


# ── Guild ────────────────────────────────────────────────────────────
# ID của server chính mà bot hoạt động
MAIN_GUILD_ID = discord.Object(id=1397175419664470031)

# ── Roles ────────────────────────────────────────────────────────────
# Role "ra đảo" — sẽ được gán cho member khi bị radao
TARGET_ROLE_ID = 1442769995783475292

# Category chứa các channel đảo
TARGET_CATEGORY_ID = 1442769574285283399

# Role "nhập kho" — sẽ được gán cho member khi bị nhập kho
NHAPKHO_ROLE_ID = 1504949883264569374

# Channel thông báo khi nhập kho
NHAPKHO_LOG_CHANNEL_ID = 1504949644709335240

# Các role được phép sử dụng lệnh /radao, /giaicuu và /nhapkho
ALLOWED_ROLE_IDS = [
    1489982960404009051,
    1397185946541359214,
    1397191790381236304,
    1450851766911369337,
]
ALLOWED_ROLE_ID_SET = frozenset(ALLOWED_ROLE_IDS)

# User ID được phép sử dụng lệnh ban bot dù không có role ở trên.
# Thêm ID Discord vào danh sách này, ví dụ:
# ALLOWED_USER_IDS = [123456789012345678, 987654321098765432]
ALLOWED_USER_IDS = [
    1093175386310971484,
]
ALLOWED_USER_ID_SET = frozenset(ALLOWED_USER_IDS)

# Các role này sẽ không được dùng lệnh ban bot, kể cả khi nằm trong ALLOWED_USER_IDS.
COMMAND_BLOCKED_ROLE_IDS = [
    TARGET_ROLE_ID,
    NHAPKHO_ROLE_ID,
]
COMMAND_BLOCKED_ROLE_ID_SET = frozenset(COMMAND_BLOCKED_ROLE_IDS)

# Các role sẽ bị gỡ khi member ra đảo hoặc nhập kho (và trả lại khi về bờ/xuất kho)
ROLES_TO_REMOVE = [
    1489982960404009051,
    1397191790381236304,
    1450851766911369337,
    1463754309245337672,
    1434043875445702656,
    1408433140363432006,
    1397191419361230970,
    1408419247163576330,
    1462487968705937418,
    1397191419361230970
]
ROLES_TO_REMOVE_ID_SET = frozenset(ROLES_TO_REMOVE)

# Các role bị bỏ qua khi so sánh quyền (không tính vào top role)
IGNORED_BANNED_ROLES = [
    1487076845123010733,
]
IGNORED_BANNED_ROLE_ID_SET = frozenset(IGNORED_BANNED_ROLES)

# Các user bị bỏ qua khi so sánh quyền, hoạt động giống IGNORED_BANNED_ROLES.
IGNORED_BANNED_USERS = []
IGNORED_BANNED_USER_ID_SET = frozenset(IGNORED_BANNED_USERS)

# ── Autoban / Honeypot ───────────────────────────────────────────────
# Channel bẫy: ai nhắn vào đây sẽ bị ra đảo vĩnh viễn, trừ role bỏ qua.
# Có thể override bằng env var AUTOBAN_CHANNEL_ID.
AUTOBAN_CHANNEL_ID = int_env_or_existing("AUTOBAN_CHANNEL_ID", 1518285558785245394)

# Mặc định bỏ qua các role quản trị lệnh để tránh tự bắn vào chân khi test.
AUTOBAN_IGNORED_ROLE_IDS = list(ALLOWED_ROLE_IDS)
AUTOBAN_IGNORED_ROLE_ID_SET = frozenset(AUTOBAN_IGNORED_ROLE_IDS)

# Số message mới nhất cần quét ở mỗi kênh khác khi autoban cleanup.
# Đổi thành None nếu muốn quét toàn bộ lịch sử có thể truy cập.
AUTOBAN_DELETE_HISTORY_LIMIT = 100

# ── Users ────────────────────────────────────────────────────────────
# User ID được phép tự ban chính mình
SELF_BAN_ALLOWED_ID = 1397455938214039723

# ── Data ─────────────────────────────────────────────────────────────
# Thư mục chứa data files. Có thể override bằng env var DATA_DIR
# Ví dụ Docker: DATA_DIR=/data  →  /data/radao_data.json
# Local dev:    mặc định "data" →  data/radao_data.json
DATA_DIR = os.getenv("DATA_DIR", "data")
