# cogs/general.py: الأوامر العامة (الآن: /ping)

import discord
from discord import app_commands
from discord.ext import commands

from utils.config import get_color


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="اختبر أن البوت يعمل واعرف سرعة استجابته")
    @app_commands.checks.cooldown(1, 5.0)  # مرة كل 5 ثوانٍ لكل عضو
    async def ping(self, interaction: discord.Interaction):
        cfg = self.bot.cfg
        embed = discord.Embed(
            title=f" {cfg['brand']['name']} يعمل",
            description="أنا جاهز.",
            color=get_color(cfg),
        )
        embed.add_field(name="سرعة الاستجابة", value=f"{round(self.bot.latency * 1000)} ms")
        embed.set_footer(text=cfg["brand"]["footer"])
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
