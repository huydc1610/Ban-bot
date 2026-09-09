import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cogs import emoji as emoji_cog


class EmojiUiTests(unittest.TestCase):
    def test_preview_matches_the_upload_card_design(self):
        emoji = emoji_cog.CustomEmoji(name="party", id=123456789012345678, animated=False)

        embed = emoji_cog.build_emoji_embed(emoji)
        view = emoji_cog.EmojiUploadView(requester_id=1, emoji=emoji)

        self.assertEqual(embed.color.value, 0x2B2D31)
        self.assertEqual(
            embed.description,
            "**Emoji name:** `party`\n"
            "**ID emoji:** `123456789012345678`\n"
            "**Emoji link:** [Can be clicked/copied](https://cdn.discordapp.com/emojis/123456789012345678.png)",
        )
        self.assertEqual(
            embed.thumbnail.url,
            "https://cdn.discordapp.com/emojis/123456789012345678.png",
        )
        self.assertEqual(view.children[0].label, "Upload to server")


class EmojiInteractionTests(unittest.IsolatedAsyncioTestCase):
    def make_interaction(self):
        permissions = SimpleNamespace(manage_expressions=True)
        return SimpleNamespace(
            user=SimpleNamespace(id=1),
            guild=SimpleNamespace(
                me=SimpleNamespace(guild_permissions=permissions),
                emojis=[],
                create_custom_emoji=AsyncMock(return_value="<:party:123456789012345679>"),
            ),
            permissions=permissions,
            app_permissions=permissions,
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            message=SimpleNamespace(edit=AsyncMock()),
        )

    async def test_upload_cards_are_public(self):
        interaction = self.make_interaction()
        cog = emoji_cog.EmojiCog(None)
        await cog.emoji.callback(
            cog, interaction, "<:party:123456789012345678> <a:dance:123456789012345679>"
        )
        self.assertFalse(interaction.response.defer.call_args.kwargs.get("ephemeral", False))
        self.assertEqual(interaction.followup.send.await_count, 2)
        for call in interaction.followup.send.call_args_list:
            self.assertFalse(call.kwargs.get("ephemeral", False))

    async def test_success_disables_and_updates_upload_button(self):
        interaction = self.make_interaction()
        emoji = emoji_cog.CustomEmoji("party", 123456789012345678, False)
        view = emoji_cog.EmojiUploadView(1, emoji)
        button = view.children[0]
        with patch.object(emoji_cog, "fetch_emoji_bytes", AsyncMock(return_value=b"image")):
            await button.callback(interaction)
        interaction.guild.create_custom_emoji.assert_awaited_once()
        self.assertTrue(button.disabled)
        self.assertEqual(button.label, "Uploaded")
        self.assertEqual(button.style, emoji_cog.discord.ButtonStyle.secondary)
        self.assertTrue(view.is_finished())
        self.assertIs(interaction.message.edit.call_args.kwargs["view"], view)


if __name__ == "__main__":
    unittest.main()
