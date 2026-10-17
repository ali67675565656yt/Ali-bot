# utils/permissions.py: نظام الصلاحيات (من يستطيع استخدام أي أمر)

import logging

from discord import app_commands

log = logging.getLogger("ayn.perms")


class NotAuthorized(app_commands.CheckFailure):
    """يُرفع عندما لا يملك العضو الدور المطلوب."""


def user_has_role(interaction, role_names):
    """هل لدى العضو أحد هذه الأدوار؟ (المقارنة لا تفرّق بين الحروف الكبيرة والصغيرة)"""
    wanted = {name.lower() for name in role_names}
    roles = getattr(interaction.user, "roles", [])
    return any(role.name.lower() in wanted for role in roles)


def admin_only():
    """يقيّد الأمر بأدوار permissions.admin_roles في config.yaml."""

    async def predicate(interaction):
        cfg = interaction.client.cfg
        if user_has_role(interaction, cfg["permissions"]["admin_roles"]):
            return True
        raise NotAuthorized()

    return app_commands.check(predicate)
