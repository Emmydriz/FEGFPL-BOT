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


@admin_required()
async def admin_approve_renewal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.replace("approve_ren_", ""))
    admin_user = update.effective_user

    async with get_db_session() as session:
        from database.models import User
        from sqlalchemy import select
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            await query.message.reply_text("⚠️ Member record not found.")
            return

        prev_status = user.membership_status
        user.membership_status = "ACTIVE"
        user.renewal_payment_status = "APPROVED"
        user.registration_status = "COMMUNITY_ACCESS_GRANTED"

        # Check if member is already in the community group chat
        is_in_group = False
        if settings.FEG_COMMUNITY_CHAT_ID and user.telegram_id:
            try:
                cm = await context.bot.get_chat_member(
                    chat_id=settings.FEG_COMMUNITY_CHAT_ID,
                    user_id=user.telegram_id
                )
                if cm and cm.status in ["member", "administrator", "creator"]:
                    is_in_group = True
            except Exception as ex:
                logger.warning(f"Group check in renewal approval for User {user.telegram_id}: {ex}")

        # Send invite link ONLY to purged/expired members who are not currently in the group
        needs_invite_link = not is_in_group and prev_status == "EXPIRED"
        community_link = None

        if needs_invite_link:
            invite = await CommunityService.create_one_time_invite(
                session=session,
                user=user,
                bot=context.bot
            )
            community_link = invite.invite_link

        member_telegram_id = user.telegram_id
        member_feg_id = user.feg_member_id
        member_full_name = user.full_name
        current_season = user.current_season or "2026/2027"

    # Backup members to JSON snapshot file
    from services.backup_service import BackupService
    await BackupService.backup_all_members_to_json()

    await query.message.edit_caption(
        caption=f"{query.message.caption}\n\n✅ **RENEWAL APPROVED** by Admin `{admin_user.id}` (@{admin_user.username or 'Admin'})",
        parse_mode="Markdown"
    )

    if needs_invite_link and community_link:
        member_msg = (
            "🎉 **MEMBERSHIP RENEWAL & RE-ENTRY APPROVED!** 🎉\n\n"
            f"Hi **{member_full_name}**! Your FEG FPL membership renewal payment for the **{current_season}** season has been verified and approved!\n\n"
            f"👤 **FEG Member ID:** `{member_feg_id}`\n"
            f"• **Membership Status:** `ACTIVE` (Renewed)\n"
            f"• **Season:** `{current_season}`\n\n"
            "Click the button below to re-join the private FEG Telegram Community:"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 RE-JOIN FEG COMMUNITY", url=community_link)]
        ])
        reply_markup = keyboard
    else:
        member_msg = (
            "🎉 **MEMBERSHIP RENEWAL APPROVED!** 🎉\n\n"
            f"Hi **{member_full_name}**! Your FEG FPL annual membership renewal for the **{current_season}** season has been verified and approved!\n\n"
            f"👤 **FEG Member ID:** `{member_feg_id}`\n"
            f"• **Membership Status:** `ACTIVE` (Renewed)\n"
            f"• **Season:** `{current_season}`\n\n"
            "Thank you for renewing! Your community access remains fully active. Good luck in the upcoming season! ⚽🏆"
        )
        reply_markup = None

    try:
        await context.bot.send_message(
            chat_id=member_telegram_id,
            text=member_msg,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Could not send renewal approval DM to member {member_telegram_id}: {e}")


@admin_required()
async def admin_reject_renewal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.replace("reject_ren_", ""))
    admin_user = update.effective_user

    async with get_db_session() as session:
        from database.models import User
        from sqlalchemy import select
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            await query.message.reply_text("⚠️ Member record not found.")
            return

        user.renewal_payment_status = "REJECTED"
        member_telegram_id = user.telegram_id

    await query.message.edit_caption(
        caption=f"{query.message.caption}\n\n❌ **RENEWAL REJECTED** by Admin `{admin_user.id}` (@{admin_user.username or 'Admin'})",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_message(
            chat_id=member_telegram_id,
            text="⚠️ **MEMBERSHIP RENEWAL REJECTED**\n\nYour renewal payment submission could not be verified by FEG Finance Admin.\nPlease re-check your transfer receipt and try submitting again using /renew.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Could not send renewal rejection DM to member {member_telegram_id}: {e}")
