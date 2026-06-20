"""
Config file cho Ban-bot.
Thay đổi các ID ở đây để phù hợp với server của bạn.
"""

import os
import discord

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

# Các role được phép sử dụng lệnh /radao, /vebo, /nhapkho và /xuatkho
ALLOWED_ROLE_IDS = [
    1489982960404009051,
    1397185946541359214,
    1397191790381236304,
    1450851766911369337,
]
ALLOWED_ROLE_ID_SET = frozenset(ALLOWED_ROLE_IDS)

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

# ── Users ────────────────────────────────────────────────────────────
# User ID được phép tự ban chính mình
SELF_BAN_ALLOWED_ID = 1397455938214039723

# ── Data ─────────────────────────────────────────────────────────────
# Thư mục chứa data files. Có thể override bằng env var DATA_DIR
# Ví dụ Docker: DATA_DIR=/data  →  /data/radao_data.json
# Local dev:    mặc định "data" →  data/radao_data.json
DATA_DIR = os.getenv("DATA_DIR", "data")
