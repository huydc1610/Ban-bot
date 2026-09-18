import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from cogs import autoban, radao


class RadaoChannelPermissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.everyone = Mock(spec=discord.Role, id=1)
        self.staff_role = Mock(spec=discord.Role, id=2)
        self.second_staff_role = Mock(spec=discord.Role, id=5)
        self.allowed_user = discord.Object(id=50)
        self.island_role = Mock(spec=discord.Role, id=3)
        self.warehouse_role = Mock(spec=discord.Role, id=4)
        self.target = Mock(
            spec=discord.Member, id=10, roles=[], voice=None,
            display_name="target", mention="<@10>",
        )
        self.moderator = Mock(spec=discord.Member, id=20)
        self.bot_member = Mock(spec=discord.Member, id=30)
        self.previous_moderator = Mock(spec=discord.Member, id=40)
        self.channel = SimpleNamespace(send=AsyncMock(), edit=AsyncMock())
        self.category = SimpleNamespace(overwrites={
            self.everyone: discord.PermissionOverwrite(view_channel=True),
            self.staff_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
            ),
            self.previous_moderator: discord.PermissionOverwrite(view_channel=True),
        })
        self.guild = SimpleNamespace(
            default_role=self.everyone,
            me=self.bot_member,
            get_role=lambda role_id: {
                radao.config.TARGET_ROLE_ID: self.island_role,
                radao.config.NHAPKHO_ROLE_ID: self.warehouse_role,
                self.staff_role.id: self.staff_role,
                self.second_staff_role.id: self.second_staff_role,
            }.get(role_id),
            get_member=lambda member_id: None,
            get_channel=lambda channel_id: self.category,
            create_text_channel=AsyncMock(return_value=self.channel),
        )
        self.interaction = SimpleNamespace(guild=self.guild, user=self.moderator)
        with patch.object(radao, "load_radao_data", return_value={}):
            self.cog = radao.RadaoCog(None)
        self.cog.add_radao_member = Mock()
        self.cog.find_radao_channel = Mock(return_value=None)
        role_update = patch.object(radao, "apply_role_update", new_callable=AsyncMock)
        role_update.start()
        self.addCleanup(role_update.stop)
        for name, value in (
            ("ALLOWED_ROLE_ID_SET", frozenset({2, 5, 999})),
            ("ALLOWED_USER_ID_SET", frozenset({50})),
        ):
            config_patch = patch.object(radao.config, name, value)
            config_patch.start()
            self.addCleanup(config_patch.stop)

    def assert_private_overwrites(self, overwrites):
        self.assertEqual(
            set(overwrites),
            {
                self.everyone, self.target, self.interaction.user, self.bot_member,
                self.staff_role, self.second_staff_role, self.allowed_user,
            },
        )
        self.assertIs(overwrites[self.everyone].view_channel, False)
        self.assertIs(overwrites[self.everyone].send_messages, False)
        for member in (
            self.target, self.interaction.user, self.bot_member,
            self.staff_role, self.second_staff_role, self.allowed_user,
        ):
            with self.subTest(member_id=member.id):
                self.assertIs(overwrites[member].view_channel, True)
                self.assertIs(overwrites[member].send_messages, True)
                self.assertIs(overwrites[member].read_message_history, True)

    async def run_manual_radao(self):
        result = await self.cog.perform_radao(
            self.interaction, self.target, None, "infinity", "test",
        )
        self.assertIs(result, self.channel)

    async def test_new_manual_island_grants_access_to_all_configured_mods(self):
        await self.run_manual_radao()

        self.guild.create_text_channel.assert_awaited_once()
        self.assertEqual(
            self.guild.create_text_channel.call_args.kwargs["name"], "dao-khi-target",
        )
        self.assert_private_overwrites(
            self.guild.create_text_channel.call_args.kwargs["overwrites"],
        )

    async def test_reused_manual_island_replaces_old_role_and_member_access(self):
        self.cog.find_radao_channel.return_value = self.channel

        await self.run_manual_radao()

        self.guild.create_text_channel.assert_not_awaited()
        self.channel.edit.assert_awaited_once()
        self.assert_private_overwrites(self.channel.edit.call_args.kwargs["overwrites"])

    async def test_self_target_retains_access(self):
        self.interaction.user = self.target

        await self.run_manual_radao()

        self.assert_private_overwrites(
            self.guild.create_text_channel.call_args.kwargs["overwrites"],
        )

    async def test_automatic_island_preserves_existing_category_permissions(self):
        result = await self.cog.perform_permanent_radao(self.guild, self.target, "test")

        self.assertIs(result, self.channel)
        overwrites = self.guild.create_text_channel.call_args.kwargs["overwrites"]
        self.assertIs(overwrites[self.staff_role].view_channel, True)
        self.assertIs(overwrites[self.target].view_channel, True)
        self.assertIs(overwrites[self.warehouse_role].view_channel, False)

    async def test_autoban_creates_island_with_the_same_mod_permissions(self):
        bot = SimpleNamespace(get_cog=lambda name: self.cog)
        cog = autoban.AutobanCog(bot)
        with patch.object(radao.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            result = await cog.radao_member(self.guild, self.target)

        self.assertIs(result, self.channel)
        sleep.assert_awaited_once_with(autoban.AUTOBAN_RADAO_SECONDS)
        self.assertEqual(
            self.guild.create_text_channel.call_args.kwargs["name"], "ban-scamer-target",
        )
        self.assertEqual(
            self.cog.add_radao_member.call_args.kwargs["expire_action"], "ban",
        )
        overwrites = self.guild.create_text_channel.call_args.kwargs["overwrites"]
        self.assert_autoban_overwrites(overwrites)

    async def test_autoban_reused_island_gets_the_same_mod_permissions(self):
        self.cog.find_radao_channel.return_value = self.channel
        bot = SimpleNamespace(get_cog=lambda name: self.cog)
        cog = autoban.AutobanCog(bot)
        with patch.object(radao.asyncio, "sleep", new_callable=AsyncMock):
            result = await cog.radao_member(self.guild, self.target)

        self.assertIs(result, self.channel)
        self.guild.create_text_channel.assert_not_awaited()
        self.channel.edit.assert_awaited_once()
        self.assert_autoban_overwrites(self.channel.edit.call_args.kwargs["overwrites"])

    def assert_autoban_overwrites(self, overwrites):
        participants = {
            self.target, self.bot_member, self.staff_role,
            self.second_staff_role, self.allowed_user,
        }
        self.assertEqual(set(overwrites), participants | {self.everyone})
        self.assertIs(overwrites[self.everyone].view_channel, False)
        self.assertIs(overwrites[self.everyone].send_messages, False)
        for participant in participants:
            with self.subTest(participant_id=participant.id):
                self.assertIs(overwrites[participant].view_channel, True)
                self.assertIs(overwrites[participant].send_messages, True)
                self.assertIs(overwrites[participant].read_message_history, True)


if __name__ == "__main__":
    unittest.main()
