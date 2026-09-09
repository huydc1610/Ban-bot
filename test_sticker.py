import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from cogs import sticker as sticker_cog


class StickerCogTests(unittest.IsolatedAsyncioTestCase):
    def make_context(self):
        permissions = SimpleNamespace(manage_expressions=True)
        source = SimpleNamespace(
            id=123456789012345678,
            name="cat",
            description="A waving cat",
            emoji="🐱",
            format=discord.StickerFormatType.png,
            url="https://cdn.discordapp.com/stickers/123456789012345678.png",
            read=AsyncMock(return_value=b"sticker-image"),
        )
        source_item = SimpleNamespace(
            fetch=AsyncMock(return_value=source),
            format=discord.StickerFormatType.png,
            id=source.id,
            name=source.name,
            read=source.read,
        )
        created = SimpleNamespace(
            id=123456789012345679,
            name="cat",
            url="https://cdn.discordapp.com/stickers/123456789012345679.png",
        )
        guild = SimpleNamespace(
            me=SimpleNamespace(guild_permissions=permissions),
            stickers=[],
            create_sticker=AsyncMock(return_value=created),
        )
        return SimpleNamespace(
            guild=guild,
            author=SimpleNamespace(id=1, guild_permissions=permissions),
            message=SimpleNamespace(
                reference=SimpleNamespace(
                    resolved=SimpleNamespace(stickers=[source_item]),
                    message_id=987654321,
                )
            ),
            send=AsyncMock(),
        )

    async def test_steal_uploads_the_sticker_from_the_replied_message(self):
        ctx = self.make_context()
        cog = sticker_cog.StickerCog(None)

        await cog.steal.callback(cog, ctx)

        created_call = ctx.guild.create_sticker.call_args
        self.assertEqual(created_call.kwargs["name"], "cat")
        self.assertEqual(created_call.kwargs["description"], "A waving cat")
        self.assertEqual(created_call.kwargs["emoji"], "🐱")
        self.assertEqual(created_call.kwargs["file"].filename, "cat.png")
        ctx.send.assert_awaited_once()
        self.assertEqual(ctx.send.call_args.args[0], "Đã upload sticker `cat` thành công.")
        embed = ctx.send.call_args.kwargs["embed"]
        self.assertEqual(embed.color.value, 0x2B2D31)
        self.assertEqual(
            embed.description,
            "**Sticker name:** `cat`\n"
            "**ID sticker:** `123456789012345679`\n"
            "**Sticker link:** [Can be clicked/copied](https://cdn.discordapp.com/stickers/123456789012345679.png)",
        )

    async def test_steal_requires_a_reply_to_a_sticker_message(self):
        ctx = self.make_context()
        ctx.message.reference = None
        cog = sticker_cog.StickerCog(None)

        await cog.steal.callback(cog, ctx)

        ctx.guild.create_sticker.assert_not_awaited()
        ctx.send.assert_awaited_once_with(
            "Hãy reply vào tin nhắn có sticker rồi dùng `!steal`."
        )


if __name__ == "__main__":
    unittest.main()
