import io

import discord
from discord.ext import commands


def has_manage_expressions(member) -> bool:
    permissions = getattr(member, "guild_permissions", None)
    return bool(getattr(permissions, "manage_expressions", False))


def build_sticker_embed(sticker) -> discord.Embed:
    embed = discord.Embed(color=0x2B2D31)
    embed.description = (
        f"**Sticker name:** `{sticker.name}`\n"
        f"**ID sticker:** `{sticker.id}`\n"
        f"**Sticker link:** [Can be clicked/copied]({sticker.url})"
    )
    embed.set_thumbnail(url=sticker.url)
    return embed


async def replied_sticker(ctx):
    reference = getattr(ctx.message, "reference", None)
    if reference is None:
        return None

    replied_message = getattr(reference, "resolved", None)
    stickers = getattr(replied_message, "stickers", ())
    if not stickers:
        try:
            replied_message = await ctx.channel.fetch_message(reference.message_id)
        except (discord.Forbidden, discord.HTTPException):
            return None
        stickers = replied_message.stickers
    return stickers[0] if stickers else None


class StickerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="steal")
    @commands.guild_only()
    async def steal(self, ctx: commands.Context):
        guild = ctx.guild
        if not has_manage_expressions(ctx.author):
            return await ctx.send("Bạn cần quyền Manage Expressions để dùng `!steal`.")
        if not has_manage_expressions(guild.me):
            return await ctx.send("Bot cần quyền Manage Expressions để upload sticker.")

        sticker_item = await replied_sticker(ctx)
        if sticker_item is None:
            return await ctx.send(
                "Hãy reply vào tin nhắn có sticker rồi dùng `!steal`."
            )
        if sticker_item.format is discord.StickerFormatType.lottie:
            return await ctx.send("Discord không cho tải sticker Lottie để upload lại.")

        try:
            source = await sticker_item.fetch()
            image = await sticker_item.read()
        except (discord.Forbidden, discord.HTTPException, TypeError):
            return await ctx.send("Không tải được sticker nguồn từ Discord.")

        emoji = getattr(source, "emoji", None)
        if not emoji:
            return await ctx.send("Sticker nguồn không có emoji tag để upload lại.")
        if any(existing.name == sticker_item.name for existing in guild.stickers):
            return await ctx.send(f"Server đã có sticker tên `{sticker_item.name}`.")

        filename = f"{sticker_item.name}.{sticker_item.format.file_extension}"
        try:
            created = await guild.create_sticker(
                name=sticker_item.name,
                description=source.description or "",
                emoji=emoji,
                file=discord.File(io.BytesIO(image), filename=filename),
                reason=f"!steal bởi {ctx.author} ({ctx.author.id})",
            )
        except discord.Forbidden:
            return await ctx.send("Bot không đủ quyền để tạo sticker trong server.")
        except discord.HTTPException as error:
            detail = getattr(error, "text", None) or "Discord từ chối yêu cầu."
            return await ctx.send(f"Không thể upload sticker: {detail}")

        await ctx.send(
            f"Đã upload sticker `{created.name}` thành công.",
            embed=build_sticker_embed(created),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(StickerCog(bot))
