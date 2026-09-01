import asyncio
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import discord
from discord import app_commands
from discord.ext import commands

import config


CUSTOM_EMOJI_RE = re.compile(
    r"<(?P<animated>a?):(?P<name>[A-Za-z0-9_]{2,32}):(?P<emoji_id>\d{17,20})>"
)
MAX_EMOJIS_PER_COMMAND = 20
MAX_EMOJI_BYTES = 256 * 1024
EMOJI_VIEW_TIMEOUT_SECONDS = 15 * 60


@dataclass(frozen=True)
class CustomEmoji:
    name: str
    id: int
    animated: bool


class EmojiDownloadError(Exception):
    pass


def parse_custom_emojis(value: str) -> list[CustomEmoji]:
    emojis = []
    seen_ids = set()
    for match in CUSTOM_EMOJI_RE.finditer(value):
        emoji_id = int(match["emoji_id"])
        if emoji_id in seen_ids:
            continue
        seen_ids.add(emoji_id)
        emojis.append(
            CustomEmoji(
                name=match["name"],
                id=emoji_id,
                animated=match["animated"] == "a",
            )
        )
    return emojis


def cdn_url(emoji_id: int, *, animated: bool) -> str:
    extension = "gif" if animated else "png"
    return f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}"


def has_manage_expressions(permissions) -> bool:
    return bool(getattr(permissions, "manage_expressions", False))


def download_emoji_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Ban-bot emoji importer"})
    try:
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get_content_type()
            image = response.read(MAX_EMOJI_BYTES + 1)
    except (HTTPError, URLError, OSError) as error:
        raise EmojiDownloadError("Không tải được emoji từ Discord CDN.") from error

    if content_type not in {"image/gif", "image/png"}:
        raise EmojiDownloadError("Discord CDN không trả về file ảnh hợp lệ.")
    if not image or len(image) > MAX_EMOJI_BYTES:
        raise EmojiDownloadError("File emoji rỗng hoặc vượt quá giới hạn dung lượng.")
    return image


async def fetch_emoji_bytes(emoji: CustomEmoji) -> bytes:
    return await asyncio.to_thread(
        download_emoji_bytes,
        cdn_url(emoji.id, animated=emoji.animated),
    )


class EmojiUploadView(discord.ui.View):
    def __init__(self, bot: commands.Bot | None, requester_id: int, emoji: CustomEmoji):
        super().__init__(timeout=EMOJI_VIEW_TIMEOUT_SECONDS)
        self.bot = bot
        self.requester_id = requester_id
        self.emoji = emoji

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id:
            return True
        await interaction.response.send_message(
            "Chỉ người đã dùng lệnh /emoji mới có thể upload emoji này.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Upload emoji", style=discord.ButtonStyle.green)
    async def upload_emoji(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "Emoji chỉ có thể được upload trong server.", ephemeral=True
            )
        if not has_manage_expressions(interaction.permissions):
            return await interaction.response.send_message(
                "Bạn cần quyền Manage Expressions để upload emoji.", ephemeral=True
            )

        bot_member = guild.me
        bot_permissions = getattr(bot_member, "guild_permissions", None)
        if not (
            has_manage_expressions(bot_permissions)
            or has_manage_expressions(interaction.app_permissions)
        ):
            return await interaction.response.send_message(
                "Bot cần quyền Manage Expressions để upload emoji.", ephemeral=True
            )
        if any(existing.name == self.emoji.name for existing in guild.emojis):
            return await interaction.response.send_message(
                f"Server đã có emoji tên `:{self.emoji.name}:`.", ephemeral=True
            )

        await interaction.response.defer()
        try:
            image = await fetch_emoji_bytes(self.emoji)
            created = await guild.create_custom_emoji(
                name=self.emoji.name,
                image=image,
                reason=f"/emoji bởi {interaction.user} ({interaction.user.id})",
            )
        except EmojiDownloadError as error:
            return await interaction.message.edit(content=str(error), view=self)
        except discord.Forbidden:
            return await interaction.message.edit(
                content="Bot không đủ quyền để tạo emoji trong server.", view=self
            )
        except discord.HTTPException as error:
            return await interaction.message.edit(
                content=f"Không thể upload `:{self.emoji.name}:`: {error.text or 'Discord từ chối yêu cầu.'}",
                view=self,
            )

        button.disabled = True
        self.stop()
        await interaction.message.edit(
            content=f"Đã upload {created} thành công.", view=self
        )


class EmojiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="emoji", description="Lấy custom emoji từ server khác vào server này."
    )
    @app_commands.guilds(config.MAIN_GUILD_ID)
    @app_commands.describe(emojis="Dán một hoặc nhiều <:ten:id> hoặc <a:ten:id>")
    async def emoji(self, interaction: discord.Interaction, emojis: str):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "Lệnh này chỉ dùng trong server.", ephemeral=True
            )
        if not has_manage_expressions(interaction.permissions):
            return await interaction.response.send_message(
                "Bạn cần quyền Manage Expressions để dùng lệnh này.", ephemeral=True
            )

        parsed_emojis = parse_custom_emojis(emojis)
        if not parsed_emojis:
            return await interaction.response.send_message(
                "Không tìm thấy custom emoji hợp lệ. Hãy dán dạng `<:ten:id>` hoặc `<a:ten:id>`.",
                ephemeral=True,
            )
        if len(parsed_emojis) > MAX_EMOJIS_PER_COMMAND:
            return await interaction.response.send_message(
                f"Mỗi lần chỉ được tối đa {MAX_EMOJIS_PER_COMMAND} emoji.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True, thinking=True)
        for emoji in parsed_emojis:
            embed = discord.Embed(title=f"Emoji: :{emoji.name}:")
            embed.set_image(url=cdn_url(emoji.id, animated=emoji.animated))
            await interaction.followup.send(
                content="Bấm nút bên dưới để upload emoji này.",
                embed=embed,
                view=EmojiUploadView(self.bot, interaction.user.id, emoji),
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiCog(bot))
