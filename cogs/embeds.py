# cogs/embeds.py: أمر /announce لنشر إعلان منسّق بهوية السيرفر

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.config import get_color
from utils.permissions import admin_only

log = logging.getLogger("ayn.embeds")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_IMAGE_BYTES = 8 * 1024 * 1024          # الحد الأقصى لحجم الصورة: 8 ميغابايت
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
EMBED_TOTAL_LIMIT = 6000                    # حد ديسكورد لمجموع حروف الـ Embed

DEFAULTS = {
    "channel_name": "announcements",
    "ping_role_name": "Release Pings",
    "logo_path": "assets/4_announcements_thumbnail_256.png",
    "logo_by_default": True,
    "show_timestamp": True,
}


@dataclass
class Draft:
    """كل ما يلزم لبناء الإعلان."""
    channel: discord.TextChannel
    color_key: str
    ping_role: Optional[discord.Role]
    title: str
    body: str
    field: Optional[tuple]          # (اسم, نص) أو None
    image: Optional[tuple]          # (اسم الملف, البيانات) أو None
    thumb: Optional[tuple]          # صورة مصغرة مخصصة أو الشعار


def check_image(att: discord.Attachment):
    """يتأكد أن المرفق صورة مناسبة، ويرفع ValueError برسالة عربية إن لم يكن."""
    ext = Path(att.filename).suffix.lower()
    if ext not in ALLOWED_EXT or (att.content_type and not att.content_type.startswith("image/")):
        raise ValueError("المرفق يجب أن يكون صورة (png أو jpg أو gif أو webp).")
    if att.size > MAX_IMAGE_BYTES:
        raise ValueError("حجم الصورة أكبر من 8 ميغابايت.")
    return ext


def build_embed(cfg, draft: Draft, show_timestamp: bool) -> discord.Embed:
    embed = discord.Embed(
        title=draft.title,
        description=draft.body,
        color=get_color(cfg, draft.color_key),
    )
    if draft.field:
        embed.add_field(name=draft.field[0], value=draft.field[1], inline=False)
    if draft.image:
        embed.set_image(url=f"attachment://{draft.image[0]}")
    if draft.thumb:
        embed.set_thumbnail(url=f"attachment://{draft.thumb[0]}")
    embed.set_footer(text=cfg["brand"]["footer"])
    if show_timestamp:
        embed.timestamp = discord.utils.utcnow()
    return embed


def make_files(draft: Draft):
    """ينشئ كائنات ملفات جديدة (الملف لا يُستخدم إلا مرة واحدة)."""
    files = []
    for item in (draft.image, draft.thumb):
        if item:
            files.append(discord.File(io.BytesIO(item[1]), filename=item[0]))
    return files


class ConfirmView(discord.ui.View):
    """زرّا «إرسال» و«إلغاء» تحت المعاينة."""

    def __init__(self, cog, draft: Draft, owner_id: int, show_timestamp: bool):
        super().__init__(timeout=180)
        self.cog = cog
        self.draft = draft
        self.owner_id = owner_id
        self.show_timestamp = show_timestamp
        self.preview_msg = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("هذه المعاينة ليست لك.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # انتهت المهلة: نزيل الأزرار
        if self.preview_msg:
            try:
                await self.preview_msg.edit(content="انتهت مهلة المعاينة. أعد كتابة /announce.", embed=None,
                                        attachments=[], view=None)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="إرسال", style=discord.ButtonStyle.success, emoji="✔")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        d = self.draft
        embed = build_embed(self.cog.bot.cfg, d, self.show_timestamp)
        mentions = discord.AllowedMentions(
            everyone=False, users=False, roles=[d.ping_role] if d.ping_role else False
        )
        try:
            msg = await d.channel.send(
                content=d.ping_role.mention if d.ping_role else None,
                embed=embed,
                files=make_files(d),
                allowed_mentions=mentions,
            )
        except discord.Forbidden:
            log.warning("فشل النشر: لا صلاحية في القناة %s", d.channel.id)
            await interaction.edit_original_response(
                content="لا أملك صلاحية النشر في هذه القناة. راجع صلاحيات دور البوت في القناة.",
                embed=None, attachments=[], view=None)
            return
        except discord.HTTPException as e:
            log.error("فشل النشر: %s", e)
            await interaction.edit_original_response(
                content="رفض ديسكورد الإرسال (غالبًا حجم الصورة أو طول النص). جرّب تقليلهما.",
                embed=None, attachments=[], view=None)
            return

        self.stop()
        log.info("تم نشر إعلان | المستخدم=%s | القناة=%s | إشارة=%s",
                 interaction.user.id, d.channel.id, bool(d.ping_role))
        await interaction.edit_original_response(
            content=f"✔ تم النشر في {d.channel.mention}: {msg.jump_url}",
            embed=None, attachments=[], view=None)

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.danger, emoji="✖")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="تم الإلغاء.", embed=None, attachments=[], view=None)


class AnnounceModal(discord.ui.Modal, title="إعلان جديد"):
    """نافذة كتابة الإعلان (تدعم الأسطر المتعددة، وهي مريحة على الهاتف)."""

    title_in = discord.ui.TextInput(
        label="العنوان", style=discord.TextStyle.short, max_length=256,
        placeholder="مثال: تحديث 0.3 متاح للتجربة")
    body_in = discord.ui.TextInput(
        label="النص", style=discord.TextStyle.paragraph, max_length=3500,
        placeholder="اكتب الإعلان هنا. يمكنك استخدام أسطر متعددة وتنسيق ديسكورد (**غامق**).")
    field_name_in = discord.ui.TextInput(
        label="عنوان حقل إضافي (اختياري)", style=discord.TextStyle.short,
        max_length=256, required=False)
    field_value_in = discord.ui.TextInput(
        label="نص الحقل الإضافي (اختياري)", style=discord.TextStyle.paragraph,
        max_length=1024, required=False)

    def __init__(self, cog, channel, color_key, ping_role, image_att, thumb_att, use_logo, show_timestamp):
        super().__init__()
        self.cog = cog
        self.channel = channel
        self.color_key = color_key
        self.ping_role = ping_role
        self.image_att = image_att
        self.thumb_att = thumb_att
        self.use_logo = use_logo
        self.show_timestamp = show_timestamp

    async def on_submit(self, interaction: discord.Interaction):
        # قراءة الصور قد تأخذ وقتًا، لذلك نؤجل الرد أولًا
        await interaction.response.defer(ephemeral=True, thinking=True)
        cfg = self.cog.bot.cfg

        # الحقل الإضافي: إما الاثنان معًا أو لا شيء
        fname = self.field_name_in.value.strip()
        fvalue = self.field_value_in.value.strip()
        if bool(fname) != bool(fvalue):
            await interaction.followup.send("الحقل الإضافي يحتاج عنوانًا ونصًا معًا، أو اتركهما فارغين.", ephemeral=True)
            return

        image = thumb = None
        try:
            if self.image_att:
                ext = check_image(self.image_att)
                image = ("image" + ext, await self.image_att.read())
            if self.thumb_att:
                ext = check_image(self.thumb_att)
                thumb = ("thumb" + ext, await self.thumb_att.read())
            elif self.use_logo:
                logo_file = PROJECT_ROOT / self.cog.acfg()["logo_path"]
                if logo_file.is_file():
                    thumb = ("logo.png", logo_file.read_bytes())
                else:
                    log.warning("ملف الشعار غير موجود: %s", logo_file)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.followup.send("تعذّر تحميل الصورة. أعد المحاولة.", ephemeral=True)
            return

        draft = Draft(
            channel=self.channel, color_key=self.color_key, ping_role=self.ping_role,
            title=self.title_in.value.strip(), body=self.body_in.value.strip(),
            field=(fname, fvalue) if fname else None, image=image, thumb=thumb,
        )
        embed = build_embed(cfg, draft, self.show_timestamp)
        if len(embed) > EMBED_TOTAL_LIMIT:
            await interaction.followup.send(
                f"الإعلان طويل جدًا ({len(embed)} حرفًا). الحد الأقصى لديسكورد {EMBED_TOTAL_LIMIT}.", ephemeral=True)
            return

        view = ConfirmView(self.cog, draft, interaction.user.id, self.show_timestamp)
        ping_note = f"\nسيتم إشارة {self.ping_role.mention}" if self.ping_role else ""
        view.preview_msg = await interaction.followup.send(
            content=f" **معاينة.** سيُنشر في {self.channel.mention}{ping_note}",
            embed=embed, files=make_files(draft), view=view, ephemeral=True, wait=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error("خطأ في نافذة الإعلان", exc_info=error)
        msg = "حصل خطأ أثناء تجهيز الإعلان."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


class Embeds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def acfg(self):
        """إعدادات الإعلانات: القيم الافتراضية ثم ما في config.yaml."""
        merged = dict(DEFAULTS)
        merged.update(self.bot.cfg.get("announce") or {})
        return merged

    @app_commands.command(name="announce", description="انشر إعلانًا منسّقًا بهوية السيرفر (للإدارة فقط)")
    @app_commands.describe(
        channel="القناة (الافتراضي: announcements)",
        color="لون الإعلان (الافتراضي: ذهبي)",
        ping="هل تُشير دور Release Pings؟ (الافتراضي: لا)",
        image="صورة كبيرة أسفل الإعلان (اختياري)",
        thumbnail="صورة مصغرة بدل الشعار (اختياري)",
        logo="إظهار شعارك كصورة مصغرة (الافتراضي بحسب الإعدادات)",
    )
    @app_commands.choices(color=[
        app_commands.Choice(name="ذهبي", value="primary"),
        app_commands.Choice(name="ذهبي داكن", value="dark"),
        app_commands.Choice(name="رمادي مزرق", value="accent"),
    ])
    @admin_only()
    @app_commands.checks.cooldown(1, 15.0)
    async def announce(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        color: Optional[app_commands.Choice[str]] = None,
        ping: bool = False,
        image: Optional[discord.Attachment] = None,
        thumbnail: Optional[discord.Attachment] = None,
        logo: Optional[bool] = None,
    ):
        a = self.acfg()
        guild = interaction.guild

        # 1) القناة المستهدفة
        target = channel or discord.utils.get(guild.text_channels, name=a["channel_name"])
        if target is None:
            await interaction.response.send_message(
                f"لم أجد القناة «{a['channel_name']}». اخترها بنفسك من خيار channel.", ephemeral=True)
            return

        # 2) صلاحيات البوت في القناة
        perms = target.permissions_for(guild.me)
        needed = {"send_messages": "Send Messages", "embed_links": "Embed Links", "attach_files": "Attach Files"}
        missing = [label for attr, label in needed.items() if not getattr(perms, attr)]
        if missing:
            await interaction.response.send_message(
                f"ينقص البوت في {target.mention} الصلاحيات: " + "، ".join(missing), ephemeral=True)
            return

        # 3) دور الإشارة
        role = None
        if ping:
            role = discord.utils.get(guild.roles, name=a["ping_role_name"])
            if role is None:
                await interaction.response.send_message(
                    f"لم أجد دور «{a['ping_role_name']}». أنشئه أو عدّل اسمه في config.yaml.", ephemeral=True)
                return
            if not (role.mentionable or perms.mention_everyone):
                await interaction.response.send_message(
                    "لا أستطيع إشارة هذا الدور. فعّل للبوت صلاحية «Mention @everyone, @here, and All Roles».",
                    ephemeral=True)
                return

        # 4) فحص الصور مبكرًا (دون تحميلها بعد)
        try:
            for att in (image, thumbnail):
                if att:
                    check_image(att)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        use_logo = a["logo_by_default"] if logo is None else logo
        modal = AnnounceModal(
            cog=self, channel=target, color_key=color.value if color else "primary",
            ping_role=role, image_att=image, thumb_att=thumbnail,
            use_logo=use_logo, show_timestamp=a["show_timestamp"],
        )
        await interaction.response.send_modal(modal)


async def setup(bot: commands.Bot):
    await bot.add_cog(Embeds(bot))
