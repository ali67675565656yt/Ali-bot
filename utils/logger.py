# utils/logger.py: إعداد التسجيل (Logging) مع إخفاء الأسرار تلقائيًا

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


class RedactingFormatter(logging.Formatter):
    """ينسّق السجل ثم يستبدل أي سر معروف بـ *** قبل الكتابة."""

    def __init__(self, fmt, secrets):
        super().__init__(fmt)
        # نتجاهل القيم القصيرة جدًا حتى لا نخفي كلمات عادية
        self.secrets = [s for s in secrets if s and len(s) >= 8]

    def format(self, record):
        text = super().format(record)  # يشمل نص الخطأ إن وُجد
        for secret in self.secrets:
            text = text.replace(secret, "***")
        return text


def setup_logging(cfg):
    level_name = cfg.get("logging", {}).get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    secrets = [os.getenv("DISCORD_TOKEN", ""), os.getenv("AI_API_KEY", "")]
    formatter = RedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", secrets)

    handlers = [logging.StreamHandler()]
    try:
        LOG_DIR.mkdir(exist_ok=True)
        # ملف سجل يدور: حد 1 ميغابايت، ويحتفظ بـ 3 نسخ قديمة
        handlers.append(
            RotatingFileHandler(LOG_DIR / "bot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        )
    except OSError:
        pass  # إن تعذّر إنشاء الملف نكتفي بالشاشة

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    for h in handlers:
        h.setFormatter(formatter)
        root.addHandler(h)
