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
        """
        Determines admin role using numeric Telegram IDs.
        If default placeholder ADMIN_SUPER_ID (123456789) is in use,
        automatically registers active admin users so they receive all DMs
        and can access admin commands.
        """
        if telegram_id == settings.ADMIN_SUPER_ID:
            return "SUPER_ADMIN"
        elif telegram_id == settings.ADMIN_FINANCE_ID:
            return "FINANCE_ADMIN"
        elif telegram_id == settings.ADMIN_CONTENT_ID:
            return "CONTENT_ADMIN"

        # Check registered dynamic admins
        if telegram_id in _DYNAMIC_ADMIN_IDS:
            return "SUPER_ADMIN"

        # Developer / Testing Auto-Promotion Mode:
        # If env has placeholder ADMIN_SUPER_ID (123456789), auto-register requesting admin user
        if settings.ADMIN_SUPER_ID == 123456789:
            cls.register_admin(telegram_id)
            logger.info(f"Auto-promoted Telegram ID {telegram_id} to SUPER_ADMIN for testing/development.")
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
        admin_set = set(_DYNAMIC_ADMIN_IDS)
        if settings.ADMIN_SUPER_ID:
            admin_set.add(settings.ADMIN_SUPER_ID)
        if settings.ADMIN_FINANCE_ID:
            admin_set.add(settings.ADMIN_FINANCE_ID)
        return list(admin_set)

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


def admin_required(required_role: Optional[str] = None):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                return

            if not AuthService.is_authorized_admin(user.id, required_role):
                logger.warning(f"Unauthorized admin command attempt by Telegram ID {user.id} ({user.full_name}).")
                await AuthService.log_unauthorized_attempt(user.id, func.__name__)
                msg = "⚠️ **ACCESS DENIED**\n\nYou are not authorized to perform this administrative command."
                if update.callback_query:
                    await update.callback_query.answer("Access Denied", show_alert=True)
                    await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
                elif update.message:
                    await update.message.reply_text(msg, parse_mode="Markdown")
                return

            context.user_role = AuthService.get_admin_role(user.id)
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

                if not user or user.registration_status not in ["APPROVED", "COMMUNITY_ACCESS_GRANTED"]:
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
