# cogs/admin.py: أوامر الإدارة (للأدوار المذكورة في permissions.admin_roles فقط)

import discord
from discord import app_commands
from discord.ext import commands

from utils.config import get_color
from utils.permissions import admin_only


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="حالة البوت وإعداداته الحالية (للإدارة فقط)")
    @admin_only()
    @app_commands.checks.cooldown(1, 10.0)
    async def status(self, interaction: discord.Interaction):
        cfg = self.bot.cfg
        ai = cfg["ai"]
        embed = discord.Embed(title=f" حالة {cfg['brand']['name']}", color=get_color(cfg))
        embed.add_field(
            name="يعمل منذ",
            value=discord.utils.format_dt(self.bot.started_at, "R"),
            inline=True,
        )
        embed.add_field(name="الاستجابة", value=f"{round(self.bot.latency * 1000)} ms", inline=True)
        embed.add_field(name="الذكاء الاصطناعي", value="مفعّل" if ai["enabled"] else "معطّل", inline=True)
        embed.add_field(
            name="الأدوار المسموح لها",
            value="، ".join(cfg["permissions"]["admin_roles"]) or "لا أحد",
            inline=False,
        )
        embed.set_footer(text=cfg["brand"]["footer"])
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
