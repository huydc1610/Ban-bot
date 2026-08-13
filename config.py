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


# =====================================================================
# 1. CẤU HÌNH CHUNG (GENERAL CONFIG)
# =====================================================================
# ID của server chính mà bot hoạt động
MAIN_GUILD_ID = discord.Object(id=1513847925791391835)

# Thư mục chứa data files.
DATA_DIR = os.getenv("DATA_DIR", "data")

# Các role được phép sử dụng lệnh /radao, /giaicuu và /nhapkho
ALLOWED_ROLE_IDS = [
    1535211798397976576,
    1536067056020095007
]
ALLOWED_ROLE_ID_SET = frozenset(ALLOWED_ROLE_IDS)

# User ID được phép sử dụng lệnh ban bot dù không có role ở trên.
ALLOWED_USER_IDS = []
ALLOWED_USER_ID_SET = frozenset(ALLOWED_USER_IDS)

# Các role bị bỏ qua khi so sánh quyền (không tính vào top role)
IGNORED_BANNED_ROLES = []
IGNORED_BANNED_ROLE_ID_SET = frozenset(IGNORED_BANNED_ROLES)

# Các user bị bỏ qua khi so sánh quyền, hoạt động giống IGNORED_BANNED_ROLES.
IGNORED_BANNED_USERS = []
IGNORED_BANNED_USER_ID_SET = frozenset(IGNORED_BANNED_USERS)

# Các role sẽ bị gỡ khi member ra đảo hoặc nhập kho (và trả lại khi về bờ/xuất kho)
ROLES_TO_REMOVE = [
    1536380806296117258,
    1535268950324019271
]
ROLES_TO_REMOVE_ID_SET = frozenset(ROLES_TO_REMOVE)

# User ID được phép tự ban chính mình
SELF_BAN_ALLOWED_ID = 1397455938214039723


# =====================================================================
# 2. COG: RA ĐẢO (radao.py)
# =====================================================================
# Role "ra đảo" — sẽ được gán cho member khi bị radao
TARGET_ROLE_ID = 1536661024655286393

# Category chứa các channel đảo
TARGET_CATEGORY_ID = 1536661272488185896


# =====================================================================
# 3. COG: NHẬP KHO (nhapkho.py)
# =====================================================================
# Role "nhập kho" — sẽ được gán cho member khi bị nhập kho
NHAPKHO_ROLE_ID = 1536660908699287572

# Channel thông báo khi nhập kho
NHAPKHO_LOG_CHANNEL_ID = 1536662211425206372


# =====================================================================
# CHẶN LỆNH (COMMAND BLOCK - Dùng cho Ra đảo & Nhập kho)
# =====================================================================
# Các role này sẽ không được dùng lệnh ban bot, kể cả khi nằm trong ALLOWED_USER_IDS.
COMMAND_BLOCKED_ROLE_IDS = [
    TARGET_ROLE_ID,
    NHAPKHO_ROLE_ID,
]
COMMAND_BLOCKED_ROLE_ID_SET = frozenset(COMMAND_BLOCKED_ROLE_IDS)


# =====================================================================
# 4. COG: AUTO BAN / HONEYPOT (autoban.py)
# =====================================================================
# Channel bẫy: ai nhắn vào đây sẽ bị ra đảo vĩnh viễn, trừ role bỏ qua.
AUTOBAN_CHANNEL_ID = int_env_or_existing("AUTOBAN_CHANNEL_ID", 1536663991408132180)

# Mặc định bỏ qua các role quản trị lệnh để tránh tự bắn vào chân khi test.
AUTOBAN_IGNORED_ROLE_IDS = list(ALLOWED_ROLE_IDS)
AUTOBAN_IGNORED_ROLE_ID_SET = frozenset(AUTOBAN_IGNORED_ROLE_IDS)

# Số message mới nhất cần quét ở mỗi kênh khác khi autoban cleanup.
AUTOBAN_DELETE_HISTORY_LIMIT = 100


# =====================================================================
# 5. COG: AUTO KICK INACTIVE (autokick.py)
# =====================================================================
# Role chỉ định cần theo dõi để kick nếu quá hạn
AUTO_KICK_ROLE_ID = 1536347679070621696

# Số ngày tối đa từ lúc tham gia server cho phép đối với role trên
AUTO_KICK_DAYS = 3

# Channel ghi log khi bot kick người dùng
CHANNEL_LOGS_BOT = int_env_or_existing("CHANNEL_LOGS_BOT", 0)
