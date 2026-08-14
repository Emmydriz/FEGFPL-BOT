from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from services.auth_service import AuthService
from config.logging_config import logger


def admin_required(required_role: str = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                return

            telegram_id = user.id
            is_authorized = AuthService.is_authorized_admin(telegram_id, required_role)

            if not is_authorized:
                action_name = update.message.text if update.message else "CallbackQuery"
                logger.warning(f"BLOCKED unauthorized admin access attempt by Telegram ID {telegram_id} for action '{action_name}'")

                await AuthService.log_unauthorized_attempt(
                    telegram_id=telegram_id,
                    action=action_name,
                    details=f"User @{user.username or 'NoUsername'} tried to invoke admin action"
                )

                blocked_msg = (
                    "🚫 **UNAUTHORISED ADMIN ACCESS ATTEMPT**\n\n"
                    f"**Telegram ID:** `{telegram_id}`\n"
                    f"**Action:** `{action_name}`\n"
                    f"**Result:** `BLOCKED`\n\n"
                    "⚠️ This incident has been logged in the FEG security audit trail."
                )

                if update.message:
                    await update.message.reply_text(blocked_msg, parse_mode="Markdown")
                elif update.callback_query:
                    await update.callback_query.answer("🚫 Unauthorised access attempt blocked.", show_alert=True)
                    await update.callback_query.message.reply_text(blocked_msg, parse_mode="Markdown")
                return

            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
