# bot.py: نقطة تشغيل البوت "عين"

import logging
import os
import sys

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.config import ConfigError, load_config

# الأقسام (cogs) التي يحمّلها البوت. نضيف هنا لاحقًا: embeds وai وغيرها
COGS = ["cogs.general"]

log = logging.getLogger("ayn")


class AynTree(app_commands.CommandTree):
    """شجرة الأوامر: تفحص كل أمر قبل تنفيذه."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cfg = self.client.cfg
        # أي أمر من خارج سيرفرك أو من الرسائل الخاصة يُرفض
        if interaction.guild_id != cfg["guild_id"]:
            await interaction.response.send_message(
                cfg["permissions"]["wrong_server_message"], ephemeral=True
            )
            log.warning("أمر مرفوض من خارج السيرفر (guild=%s)", interaction.guild_id)
            return False
        return True

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # الرد على الرفض تم أعلاه، فلا نكرره
        if isinstance(error, app_commands.CheckFailure):
            return
        # نسجل الخطأ في السجل فقط، ولا نعرض تفاصيله للعضو
        log.error("خطأ في الأمر %s", getattr(interaction.command, "name", "؟"), exc_info=error)
        msg = "حصل خطأ غير متوقع، حاول مرة ثانية بعد قليل."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


class AynBot(commands.Bot):
    def __init__(self, cfg: dict):
        # الصلاحيات الافتراضية فقط، بدون أي Intent حساس
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
            tree_cls=AynTree,
        )
        self.cfg = cfg
        self.guild_obj = discord.Object(id=cfg["guild_id"])

    async def setup_hook(self):
        # تحميل الأقسام
        for cog in COGS:
            await self.load_extension(cog)
            log.info("تم تحميل القسم: %s", cog)
        # تسجيل الأوامر في سيرفرك فقط (لا أوامر عامة)
        self.tree.copy_global_to(guild=self.guild_obj)
        synced = await self.tree.sync(guild=self.guild_obj)
        log.info("تمت مزامنة %d أمر في السيرفر", len(synced))

    async def on_ready(self):
        log.info("البوت جاهز باسم: %s", self.user)
        # مغادرة أي سيرفر آخر (للأمان)
        for guild in self.guilds:
            if guild.id != self.cfg["guild_id"]:
                log.warning("مغادرة سيرفر غير مسموح: %s", guild.id)
                await guild.leave()

    async def on_guild_join(self, guild: discord.Guild):
        if guild.id != self.cfg["guild_id"]:
            log.warning("تمت دعوتي لسيرفر غير مسموح، سأغادر: %s", guild.id)
            await guild.leave()


def main():
    load_dotenv()  # يقرأ ملف .env إن وُجد (للاختبار على الهاتف)

    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"خطأ في الإعدادات: {e}")
        sys.exit(1)

    logging.basicConfig(
        level=getattr(logging, cfg.get("logging", {}).get("level", "INFO").upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token.startswith("ضع_"):
        print("لم أجد DISCORD_TOKEN. ضعه في ملف .env (أو في متغيرات الاستضافة).")
        sys.exit(1)

    # log_handler=None لأننا ضبطنا السجل بأنفسنا
    AynBot(cfg).run(token, log_handler=None)


if __name__ == "__main__":
    main()
