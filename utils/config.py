# utils/config.py
# قراءة ملف الإعدادات config.yaml والتحقق منه.

from pathlib import Path
import yaml

# مسار config.yaml: المجلد الذي يعلو utils مباشرة
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

# الإعدادات التي لا يعمل البوت بدونها
REQUIRED = [
    ("guild_id",),
    ("brand", "name"),
    ("brand", "colors", "primary"),
    ("ai", "enabled"),
]


class ConfigError(Exception):
    """خطأ في ملف الإعدادات، ورسالته مكتوبة بالعربية."""


def load_config(path=CONFIG_PATH):
    """يقرأ الملف ويتحقق منه ويعيده على شكل قاموس."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise ConfigError(f"ملف الإعدادات غير موجود: {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"خطأ في كتابة config.yaml (غالبًا في المسافات أو علامات الاقتباس): {e}")

    # التأكد من وجود الإعدادات الأساسية
    for keys in REQUIRED:
        node = cfg
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                raise ConfigError("إعداد ناقص في config.yaml: " + " ← ".join(keys))
            node = node[k]

    if not isinstance(cfg["guild_id"], int):
        raise ConfigError("guild_id يجب أن يكون رقمًا فقط بدون علامات اقتباس")

    return cfg


def hex_to_int(value):
    """يحوّل لونًا مثل #D9B96E إلى رقم يفهمه ديسكورد."""
    try:
        return int(str(value).lstrip("#"), 16)
    except ValueError:
        raise ConfigError(f"لون غير صحيح في config.yaml: {value}")


def get_color(cfg, name="primary"):
    """يرجع لونًا من brand.colors بحسب اسمه."""
    return hex_to_int(cfg["brand"]["colors"][name])
