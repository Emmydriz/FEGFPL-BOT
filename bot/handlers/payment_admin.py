from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.middlewares.admin_auth import admin_required
from services.auth_service import AuthService
from services.payment_service import PaymentService
from services.community_service import CommunityService
from database.db import get_db_session
from config.settings import settings
from config.logging_config import logger


@admin_required()
async def admin_approve_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    payment_id = int(data.replace("approve_pay_", ""))
    admin_user = update.effective_user
    admin_role = AuthService.get_admin_role(admin_user.id)
    if admin_role not in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
        await query.answer("⚠️ Only Super Admin and Finance Admin can approve member payments.", show_alert=True)
        return

    async with get_db_session() as session:
        success, payment, user = await PaymentService.approve_payment(
            session=session,
            payment_id=payment_id,
            admin_id=admin_user.id,
            admin_role=admin_role
        )

        if not success or not user:
            await query.message.reply_text("⚠️ Payment record not found or already processed.")
            return

        # Generate member-specific community invite
        invite = await CommunityService.create_one_time_invite(
            session=session,
            user=user,
            bot=context.bot
        )
        community_link = invite.invite_link
        member_telegram_id = user.telegram_id
        member_name = user.full_name
        member_feg_id = user.feg_member_id

    # Backup members to JSON snapshot file
    from services.backup_service import BackupService
    await BackupService.backup_all_members_to_json()

    # 1. Update Admin DM UI
    await query.message.edit_caption(
        caption=(
            f"{query.message.caption}\n\n"
            f"✅ **APPROVED** by Admin `{admin_user.id}` (@{admin_user.username or 'Admin'})"
        ),
        parse_mode="Markdown"
    )

    # 2. Notify Approved Member with single-use invite link
    member_msg = (
        "🎉 **REGISTRATION APPROVED** 🎉\n\n"
        "Your FEG FPL registration payment has been verified and approved!\n"
        "Welcome to the **FEG FPL Community**.\n\n"
        f"👤 **FEG Member ID:** `{member_feg_id}`\n\n"
        "Click the button below to join the private FEG Telegram Community:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 ENTER FEG COMMUNITY", url=community_link)]
    ])

    try:
        await context.bot.send_message(
            chat_id=member_telegram_id,
            text=member_msg,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Could not send approval DM to member {member_telegram_id}: {e}")


@admin_required()
async def admin_reject_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    payment_id = int(data.replace("reject_pay_", ""))
    admin_user = update.effective_user
    admin_role = AuthService.get_admin_role(admin_user.id)

    async with get_db_session() as session:
        success, payment, user = await PaymentService.reject_payment(
            session=session,
            payment_id=payment_id,
            admin_id=admin_user.id,
            admin_role=admin_role,
            reason="Invalid proof or unconfirmed bank transfer"
        )

        if not success or not user:
            await query.message.reply_text("⚠️ Payment record not found or already processed.")
            return

        member_telegram_id = user.telegram_id

    # 1. Update Admin DM UI
    await query.message.edit_caption(
        caption=(
            f"{query.message.caption}\n\n"
            f"❌ **REJECTED** by Admin `{admin_user.id}` (@{admin_user.username or 'Admin'})"
        ),
        parse_mode="Markdown"
    )

    # 2. Notify Rejected Member
    member_msg = (
        "⚠️ **REGISTRATION PAYMENT REJECTED**\n\n"
        "Your payment submission could not be verified by FEG Finance Admin.\n"
        "Reason: Unconfirmed bank transfer or invalid receipt screenshot.\n\n"
        "Please re-check your transfer receipt details and submit again using /start."
    )

    try:
        await context.bot.send_message(
            chat_id=member_telegram_id,
            text=member_msg,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Could not send rejection DM to member {member_telegram_id}: {e}")
