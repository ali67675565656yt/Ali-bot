# bot.py: نقطة تشغيل البوت "عين"

import logging
import os
import sys

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.config import ConfigError, load_config
from utils.logger import setup_logging
from utils.permissions import NotAuthorized

# الأقسام (cogs) التي يحمّلها البوت. نضيف هنا لاحقًا: embeds وai وغيرها
COGS = ["cogs.general", "cogs.admin"]

log = logging.getLogger("ayn")


class AynTree(app_commands.CommandTree):
    """شجرة الأوامر: تفحص كل أمر قبل تنفيذه وتعالج أخطاءه."""

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
        cfg = self.client.cfg
        name = getattr(interaction.command, "name", "؟")

        if isinstance(error, NotAuthorized):
            # عضو بدون الصلاحية المطلوبة
            msg = cfg["permissions"]["denied_message"]
            log.warning("رفض صلاحية: المستخدم %s حاول /%s", interaction.user.id, name)
        elif isinstance(error, app_commands.CommandOnCooldown):
            # حماية من التكرار السريع
            msg = f"تمهّل قليلًا، حاول بعد {error.retry_after:.0f} ثانية."
            log.info("Cooldown: المستخدم %s على /%s", interaction.user.id, name)
        elif isinstance(error, app_commands.CheckFailure):
            return  # الرد تم داخل interaction_check
        else:
            # نسجل الخطأ في السجل فقط، ولا نعرض تفاصيله للعضو
            log.error("خطأ في الأمر /%s", name, exc_info=error)
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
        self.started_at = discord.utils.utcnow()  # لعرض مدة التشغيل

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

    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        # سجل الاستخدام: نسجل المعرّفات فقط، لا محتوى الرسائل
        log.info(
            "تم تنفيذ /%s | المستخدم=%s | القناة=%s",
            command.name, interaction.user.id, interaction.channel_id,
        )


def main():
    load_dotenv()  # يقرأ ملف .env إن وُجد (للاختبار على الهاتف)

    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"خطأ في الإعدادات: {e}")
        sys.exit(1)

    setup_logging(cfg)

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token.startswith("ضع_"):
        print("لم أجد DISCORD_TOKEN. ضعه في ملف .env (أو في متغيرات الاستضافة).")
        sys.exit(1)

    # log_handler=None لأننا ضبطنا السجل بأنفسنا
    AynBot(cfg).run(token, log_handler=None)


if __name__ == "__main__":
    main()
