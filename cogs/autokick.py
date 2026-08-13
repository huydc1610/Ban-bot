import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
import config

class AutoKick(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_and_kick.start()

    def cog_unload(self):
        self.check_and_kick.cancel()

    @tasks.loop(hours=1)
    async def check_and_kick(self):
        await self.bot.wait_until_ready()
        
        if not config.AUTO_KICK_ROLE_ID or not config.MAIN_GUILD_ID:
            return

        guild_id = config.MAIN_GUILD_ID.id if isinstance(config.MAIN_GUILD_ID, discord.Object) else config.MAIN_GUILD_ID
        guild = self.bot.get_guild(guild_id)
        
        if not guild:
            return

        role_to_check = guild.get_role(config.AUTO_KICK_ROLE_ID)
        if not role_to_check:
            return
            
        log_channel = None
        if config.CHANNEL_LOGS_BOT:
            log_channel = guild.get_channel(config.CHANNEL_LOGS_BOT)

        now = datetime.now(timezone.utc)
        threshold = timedelta(days=config.AUTO_KICK_DAYS)
        
        kicked_count = 0
        
        for member in guild.members:
            if role_to_check in member.roles:
                if member.joined_at and (now - member.joined_at) > threshold:
                    try:
                        await member.kick(reason=f"Auto-kick: Quá {config.AUTO_KICK_DAYS} ngày không verify")
                        kicked_count += 1
                        print(f"[AutoKick] kicked {member.name} ({member.id}) for not verifying within {config.AUTO_KICK_DAYS} days")
                        
                        if log_channel:
                            embed = discord.Embed(
                                title="AUTO-KICK",
                                description=f"Đã sút {member.mention} (`{member.id}`) ra khỏi server",
                                color=discord.Color.red()
                            )
                            embed.add_field(name="Lý do", value=f"Quá {config.AUTO_KICK_DAYS} ngày không verify", inline=False)
                            embed.add_field(name="Ngày tham gia", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=False)
                            await log_channel.send(embed=embed)
                    except discord.Forbidden:
                        print(f"[AutoKick] Lỗi: Không đủ quyền để kick {member.name} ({member.id})")
                    except Exception as e:
                        print(f"[AutoKick] Lỗi khi kick {member.name} ({member.id}): {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoKick(bot))
