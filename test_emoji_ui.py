import unittest

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


if __name__ == "__main__":
    unittest.main()
