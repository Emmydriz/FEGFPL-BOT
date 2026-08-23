import functools
from typing import Optional, List, Set
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import settings
from database.db import get_db_session
from database.repository import add_audit_log
from config.logging_config import logger

# Global set of dynamic admin IDs registered during runtime
_DYNAMIC_ADMIN_IDS: Set[int] = set()


class AuthService:
    @classmethod
    def register_admin(cls, telegram_id: int):
        _DYNAMIC_ADMIN_IDS.add(telegram_id)

    @classmethod
    def get_admin_role(cls, telegram_id: int) -> Optional[str]:
        # Production Super Admins
        super_admins = {settings.ADMIN_SUPER_ID, 1703339441, 6948840492, 123456789}
        if telegram_id in super_admins:
            cls.register_admin(telegram_id)
            return "SUPER_ADMIN"

        # Production Finance Admins
        finance_admins = {settings.ADMIN_FINANCE_ID, 2142855199, 2112337065}
        if telegram_id in finance_admins:
            cls.register_admin(telegram_id)
            return "FINANCE_ADMIN"

        # Production Content Admins
        content_admins = {settings.ADMIN_CONTENT_ID, 7017254512, 7413474541}
        if telegram_id in content_admins:
            cls.register_admin(telegram_id)
            return "CONTENT_ADMIN"

        # Check registered dynamic admins
        if telegram_id in _DYNAMIC_ADMIN_IDS:
            return "SUPER_ADMIN"

        return None

    @classmethod
    def is_authorized_admin(cls, telegram_id: int, required_role: Optional[str] = None) -> bool:
        role = cls.get_admin_role(telegram_id)
        if not role:
            return False
        if role == "SUPER_ADMIN":
            return True
        if required_role and role != required_role:
            return False
        return True

    @classmethod
    def get_all_admin_ids(cls) -> List[int]:
        """
        Returns list of all active Telegram IDs that should receive Admin DM notifications.
        """
        import os
        admin_set = set(_DYNAMIC_ADMIN_IDS)
        if settings.ADMIN_SUPER_ID:
            admin_set.add(settings.ADMIN_SUPER_ID)
        if settings.ADMIN_FINANCE_ID:
            admin_set.add(settings.ADMIN_FINANCE_ID)
        if settings.ADMIN_CONTENT_ID:
            admin_set.add(settings.ADMIN_CONTENT_ID)

        raw_env_ids = os.getenv("ADMIN_TELEGRAM_IDS", "")
        if raw_env_ids:
            for item in raw_env_ids.split(","):
                item_str = item.strip()
                if item_str.isdigit():
                    admin_set.add(int(item_str))

        return [aid for aid in admin_set if aid and aid > 0 and aid != 123456789]

    @classmethod
    def get_payment_admin_ids(cls) -> List[int]:
        """
        Returns list of Telegram IDs for Super Admin and Finance Admin ONLY
        who are authorized to receive and review payment proof notifications.
        Excludes Content Admins.
        """
        admin_set = set()
        if settings.ADMIN_SUPER_ID:
            admin_set.add(settings.ADMIN_SUPER_ID)
        if settings.ADMIN_FINANCE_ID:
            admin_set.add(settings.ADMIN_FINANCE_ID)

        for aid in _DYNAMIC_ADMIN_IDS:
            role = cls.get_admin_role(aid)
            if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
                admin_set.add(aid)

        return [aid for aid in admin_set if aid and aid > 0 and aid != 123456789]

    @staticmethod
    async def log_unauthorized_attempt(telegram_id: int, action: str, details: Optional[str] = None):
        async with get_db_session() as session:
            await add_audit_log(
                session=session,
                admin_id=telegram_id,
                role="UNAUTHORIZED",
                action="UNAUTHORISED_ADMIN_ACCESS_ATTEMPT",
                target=action,
                details=details or f"Unauthorized attempt to access {action}"
            )


def admin_required(*allowed_roles):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user or not AuthService.is_authorized_admin(user.id):
                target_msg = update.callback_query.message if update.callback_query else update.message
                if update.callback_query:
                    await update.callback_query.answer("Unauthorized", show_alert=True)
                await target_msg.reply_text("⛔ **UNAUTHORIZED:** Admin access required.", parse_mode="Markdown")
                return

            if allowed_roles:
                user_role = AuthService.get_admin_role(user.id)
                if user_role not in allowed_roles:
                    target_msg = update.callback_query.message if update.callback_query else update.message
                    if update.callback_query:
                        await update.callback_query.answer("Unauthorized Role", show_alert=True)
                    await target_msg.reply_text(f"⛔ **UNAUTHORIZED:** Requires role: {', '.join(allowed_roles)}", parse_mode="Markdown")
                    return

            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


def approved_member_required():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_tg = update.effective_user
            if not user_tg:
                return

            if AuthService.is_authorized_admin(user_tg.id):
                return await func(update, context, *args, **kwargs)

            async with get_db_session() as session:
                from services.member_service import MemberService
                user = await MemberService.get_user_by_telegram_id(session, user_tg.id)

                is_member_approved = user and (
                    user.registration_status in ["APPROVED", "COMMUNITY_ACCESS_GRANTED"] or
                    user.membership_status in ["ACTIVE", "PENDING_RENEWAL"]
                )

                if not is_member_approved:
                    # Automatic Community Group Member Restoration Check
                    if settings.FEG_COMMUNITY_CHAT_ID and context.bot:
                        try:
                            chat_member = await context.bot.get_chat_member(
                                chat_id=settings.FEG_COMMUNITY_CHAT_ID,
                                user_id=user_tg.id
                            )
                            if chat_member and chat_member.status in ["member", "administrator", "creator"]:
                                if not user:
                                    user = await MemberService.get_or_start_registration(
                                        session=session,
                                        telegram_id=user_tg.id,
                                        full_name=user_tg.full_name,
                                        telegram_username=user_tg.username
                                    )
                                user.registration_status = "COMMUNITY_ACCESS_GRANTED"
                                await session.commit()
                                logger.info(f"Auto-restored member account for Telegram User ID {user_tg.id} in decorator check.")
                                return await func(update, context, *args, **kwargs)
                        except Exception as ex:
                            logger.warning(f"Could not verify group chat membership in decorator for User {user_tg.id}: {ex}")

                    msg = (
                        "🔒 **RESTRICTED MEMBER COMMAND**\n\n"
                        "This command is exclusive to verified paid members of the FEG FPL Community.\n\n"
                        "Please complete your registration and payment verification to unlock all member commands and features!\n\n"
                        "👉 Type `/start` or `/register` to begin registration, or `/pay` to view receiving bank details."
                    )
                    target_msg = update.callback_query.message if update.callback_query else update.message
                    if update.callback_query:
                        await update.callback_query.answer("Access Restricted - Verification Required", show_alert=True)
                    await target_msg.reply_text(msg, parse_mode="Markdown")
                    return

            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
