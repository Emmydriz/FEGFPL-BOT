import datetime
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from config.settings import settings
from config.logging_config import logger
from database.db import get_db_session
from database.models import User, FPLProfile, PayoutAccount
from database.crypto import decrypt_string
from services.fpl_service import FPLService
from services.member_service import MemberService
from services.payment_service import PaymentService
from database.repository import get_latest_active_payment_account, create_payment_account_config, sync_payment_account_from_settings
from sqlalchemy import select

# Conversation States
(
    FULL_NAME,
    FPL_ID,
    BANK_NAME,
    ACCOUNT_NAME,
    ACCOUNT_NUMBER,
    VERIFY_DETAILS,
    PAYMENT_PROOF
) = range(7)


async def safe_send_markdown(target_msg, text: str, reply_markup=None):
    try:
        await target_msg.reply_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as err:
        logger.warning(f"Markdown rendering error: {err}. Falling back to plain text.")
        plain_text = text.replace("**", "").replace("`", "")
        await target_msg.reply_text(text=plain_text, reply_markup=reply_markup)


async def start_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    msg = (
        "👤 **FULL NAME**\n\n"
        "Please enter your full name.\n"
        "Use the same name associated with your FEG registration and bank details.\n\n"
        "ℹ️ **Reassurance Note:** Do not worry if you make a mistake! "
        "You will be shown a full summary screen to review and edit all your details before making any payment."
    )

    target_msg = query.message if query else update.message
    await safe_send_markdown(target_msg, msg)
    return FULL_NAME


async def help_fpl_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    msg = (
        "❓ **HOW TO FIND YOUR FPL ID**\n\n"
        "1. Open the official Fantasy Premier League website or app.\n"
        "2. Log into your FPL account.\n"
        "3. Open your FPL team/profile page (`Pick Team` or `Points`).\n"
        "4. Look at the browser URL or profile information.\n"
        "5. Example URL: `https://fantasy.premierleague.com/entry/12345678/history`\n"
        "6. Your FPL ID is the number in the middle: `12345678`.\n"
        "7. Return to FEG and enter the numerical ID."
    )
    await safe_send_markdown(query.message, msg)


async def full_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    if len(full_name) < 2:
        await update.message.reply_text("⚠️ Please enter a valid full name.")
        return FULL_NAME

    context.user_data["full_name"] = full_name
    telegram_id = update.effective_user.id

    if context.user_data.get("editing"):
        context.user_data["editing"] = False
        return await show_verify_details_screen(update, context)

    msg = (
        f"📱 **TELEGRAM ACCOUNT**\n\n"
        f"Telegram ID detected: `{telegram_id}`\n"
        "✅ Automatically recorded.\n\n"
        "⚽ **FANTASY PREMIER LEAGUE ID**\n\n"
        "Please enter your numerical FPL ID."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ HOW TO FIND MY FPL ID", callback_data="help_fpl_id")]
    ])

    await safe_send_markdown(update.message, msg, reply_markup=keyboard)
    return FPL_ID


async def fpl_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()
    if not text_input.isdigit():
        await update.message.reply_text(
            "⚠️ FPL ID must contain numbers only.\nPlease check your FPL ID and try again."
        )
        return FPL_ID

    fpl_id = int(text_input)
    context.user_data["fpl_id"] = fpl_id

    await update.message.reply_text("🔍 Fetching FPL team info from Fantasy Premier League server...")
    manager_name, team_name = await FPLService.get_user_fpl_details(fpl_id)

    if not manager_name or manager_name == "Unknown Manager":
        await update.message.reply_text(
            f"⚠️ Could not find an active FPL entry for ID `{fpl_id}`.\n"
            "Please verify your FPL ID and try again.",
            parse_mode="Markdown"
        )
        return FPL_ID

    context.user_data["manager_name"] = manager_name
    context.user_data["team_name"] = team_name

    if context.user_data.get("editing"):
        context.user_data["editing"] = False
        return await show_verify_details_screen(update, context)

    msg = (
        "✅ **FPL VERIFIED**\n\n"
        f"• Manager: {manager_name}\n"
        f"• Team: {team_name}\n\n"
        "🏦 **PAYOUT BANK DETAILS**\n\n"
        "These details will be used to pay out your rewards if you win.\n\n"
        "Please enter your **Bank Name** (e.g., Access Bank, GTBank, Zenith Bank):"
    )
    await safe_send_markdown(update.message, msg)
    return BANK_NAME


async def bank_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bank_name = update.message.text.strip()
    if len(bank_name) < 2:
        await update.message.reply_text("⚠️ Please enter a valid bank name.")
        return BANK_NAME

    context.user_data["bank_name"] = bank_name
    await update.message.reply_text(
        "👤 **PAYOUT ACCOUNT NAME**\n\n"
        "Please enter your Account Name (matching your payout bank account):"
    )
    return ACCOUNT_NAME


async def account_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_name = update.message.text.strip()
    if len(account_name) < 2:
        await update.message.reply_text("⚠️ Please enter a valid account name.")
        return ACCOUNT_NAME

    context.user_data["account_name"] = account_name
    await update.message.reply_text(
        "🔢 **PAYOUT ACCOUNT NUMBER**\n\n"
        "Please enter your Account Number (numerical):"
    )
    return ACCOUNT_NUMBER


async def account_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_num = update.message.text.strip()
    if not account_num.isdigit() or len(account_num) < 8:
        await update.message.reply_text("⚠️ Please enter a valid account number (numerical).")
        return ACCOUNT_NUMBER

    context.user_data["account_number"] = account_num
    return await show_verify_details_screen(update, context)


async def show_verify_details_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    async with get_db_session() as session:
        user = await MemberService.get_user_by_telegram_id(session, user_id)
        fpl = None
        payout = None
        if user:
            stmt_fpl = select(FPLProfile).where(FPLProfile.user_id == user.id)
            fpl = (await session.execute(stmt_fpl)).scalar_one_or_none()

            stmt_payout = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
            payout = (await session.execute(stmt_payout)).scalar_one_or_none()

    full_name = context.user_data.get("full_name") or (user.full_name if user else update.effective_user.full_name)
    fpl_id = context.user_data.get("fpl_id") or (fpl.fpl_id if fpl else "N/A")
    manager_name = context.user_data.get("manager_name") or (fpl.manager_name if fpl else "N/A")
    team_name = context.user_data.get("team_name") or (fpl.team_name if fpl else "N/A")
    bank_name = context.user_data.get("bank_name") or (payout.bank_name if payout else "N/A")
    account_name = context.user_data.get("account_name") or (payout.account_name if payout else "N/A")
    account_num = context.user_data.get("account_number") or (payout.masked_account_number if payout else "N/A")

    msg = (
        "📋 **VERIFY YOUR REGISTRATION DETAILS**\n\n"
        "Please review your information carefully before proceeding to payment:\n\n"
        f"👤 **Full Name:** {full_name}\n"
        f"📱 **Telegram ID:** `{user_id}` (Auto-captured)\n"
        f"⚽ **FPL ID:** `{fpl_id}`\n"
        f"👤 **FPL Manager:** {manager_name}\n"
        f"🛡️ **FPL Team:** {team_name}\n\n"
        "🏦 **PAYOUT BANK DETAILS:**\n"
        f"• **Bank:** {bank_name}\n"
        f"• **Account Name:** {account_name}\n"
        f"• **Account Number:** `{account_num}`\n\n"
        "If any detail is incorrect, click an **EDIT** button below. "
        "Otherwise, click **CONFIRM & PROCEED TO PAYMENT**."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ CONFIRM & PROCEED TO PAYMENT ➡️", callback_data="confirm_details")],
        [InlineKeyboardButton("✏️ EDIT FULL NAME", callback_data="edit_full_name"), InlineKeyboardButton("✏️ EDIT FPL ID", callback_data="edit_fpl_id")],
        [InlineKeyboardButton("✏️ EDIT BANK DETAILS", callback_data="edit_bank_details")]
    ])

    target_msg = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()

    await safe_send_markdown(target_msg, msg, reply_markup=keyboard)
    return VERIFY_DETAILS


async def edit_full_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["editing"] = True
    await safe_send_markdown(query.message, "✏️ **EDIT FULL NAME**\n\nPlease enter your updated Full Name:")
    return FULL_NAME


async def edit_fpl_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["editing"] = True
    await safe_send_markdown(query.message, "✏️ **EDIT FPL ID**\n\nPlease enter your updated numerical FPL ID:")
    return FPL_ID


async def edit_bank_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["editing"] = True
    await safe_send_markdown(query.message, "✏️ **EDIT BANK DETAILS**\n\nStep 1/3: Enter your updated Bank Name:")
    return BANK_NAME


async def confirm_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    telegram_id = update.effective_user.id
    tg_user = update.effective_user

    async with get_db_session() as session:
        user = await MemberService.get_user_by_telegram_id(session, telegram_id)
        full_name = context.user_data.get("full_name") or (user.full_name if user else tg_user.full_name)

        if not user:
            user = await MemberService.get_or_start_registration(
                session=session,
                telegram_id=telegram_id,
                full_name=full_name,
                telegram_username=tg_user.username
            )
        else:
            user.full_name = full_name
            user.telegram_username = tg_user.username
            user.registration_status = "PENDING_PAYMENT_PROOF"
            await session.flush()

        ref_code = context.user_data.get("referrer_code")
        if ref_code and not user.referred_by_id:
            from services.referral_service import ReferralService
            await ReferralService.record_referral(
                session=session,
                referrer_code=ref_code,
                new_user=user
            )

        fpl_id = context.user_data.get("fpl_id")
        if fpl_id:
            await MemberService.update_fpl_profile(
                session=session,
                user=user,
                fpl_id=fpl_id,
                manager_name=context.user_data.get("manager_name", "FPL Manager"),
                team_name=context.user_data.get("team_name", "FEG Team")
            )

        bank_name = context.user_data.get("bank_name")
        if bank_name:
            await MemberService.save_payout_account(
                session=session,
                user=user,
                bank_name=bank_name,
                account_name=context.user_data.get("account_name", full_name),
                account_number=context.user_data.get("account_number", "0000000000")
            )

        active_config = await sync_payment_account_from_settings(session)
        pay_bank = active_config.bank_name if (active_config and active_config.bank_name) else settings.FEG_PAYMENT_BANK
        pay_name = active_config.account_name if (active_config and active_config.account_name) else settings.FEG_PAYMENT_ACCOUNT_NAME
        pay_num = active_config.account_number if (active_config and active_config.account_number) else settings.FEG_PAYMENT_ACCOUNT_NUMBER

    msg = (
        "💳 **FEG FPL REGISTRATION PAYMENT & RECEIVING ACCOUNT** 🏦\n\n"
        f"Registration Fee: **₦{settings.FEG_REGISTRATION_FEE:,}**\n\n"
        "Please transfer exactly ₦5,000 to our official receiving bank account:\n\n"
        f"🏦 **Bank:** {pay_bank}\n"
        f"👤 **Account Name:** {pay_name}\n"
        f"🔢 **Account Number:** `{pay_num}`\n\n"
        "───────────────────────────\n"
        "📌 **PAYMENT & VERIFICATION STEPS:**\n"
        "1️⃣ Tap the Account Number above to copy it.\n"
        "2️⃣ Complete the ₦5,000 bank transfer via your bank app or USSD.\n"
        "3️⃣ Take a screenshot or photo of your payment transfer receipt.\n"
        "4️⃣ **Drop/Upload your receipt screenshot directly here in this chat.**\n\n"
        "⏳ *FEG Admins will verify your receipt and send your instant community access link!*"
    )

    target_msg = query.message if query else update.message
    await safe_send_markdown(target_msg, msg)
    return PAYMENT_PROOF


async def show_payment_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with get_db_session() as session:
        active_config = await sync_payment_account_from_settings(session)
        pay_bank = active_config.bank_name if (active_config and active_config.bank_name) else settings.FEG_PAYMENT_BANK
        pay_name = active_config.account_name if (active_config and active_config.account_name) else settings.FEG_PAYMENT_ACCOUNT_NAME
        pay_num = active_config.account_number if (active_config and active_config.account_number) else settings.FEG_PAYMENT_ACCOUNT_NUMBER

    msg = (
        "💳 **FEG FPL RECEIVING PAYMENT ACCOUNT** 🏦\n\n"
        f"Registration Fee: **₦{settings.FEG_REGISTRATION_FEE:,}**\n\n"
        f"🏦 **Bank:** {pay_bank}\n"
        f"👤 **Account Name:** {pay_name}\n"
        f"🔢 **Account Number:** `{pay_num}`\n\n"
        "📷 **Drop your transfer receipt photo/screenshot here in DM after payment for instant admin verification.**"
    )
    target_msg = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()

    await safe_send_markdown(target_msg, msg)


async def payment_proof_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proof_file_id = None
    is_document = False

    if update.message.photo:
        proof_file_id = update.message.photo[-1].file_id
    elif update.message.document:
        proof_file_id = update.message.document.file_id
        is_document = True

    if not proof_file_id:
        await update.message.reply_text(
            "📷 Please upload a photo, screenshot, or document file of your bank transfer receipt."
        )
        return PAYMENT_PROOF

    telegram_id = update.effective_user.id

    is_renewal = context.user_data.get("is_renewal", False)

    async with get_db_session() as session:
        user = await MemberService.get_user_by_telegram_id(session, telegram_id)
        if not user:
            user = await MemberService.get_or_start_registration(
                session=session,
                telegram_id=telegram_id,
                full_name=context.user_data.get("full_name", update.effective_user.full_name),
                telegram_username=update.effective_user.username
            )

        if is_renewal:
            user.renewal_payment_status = "PENDING_APPROVAL"

        stmt_fpl = select(FPLProfile).where(FPLProfile.user_id == user.id)
        fpl = (await session.execute(stmt_fpl)).scalar_one_or_none()

        stmt_payout = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        payout = (await session.execute(stmt_payout)).scalar_one_or_none()

        payment = await PaymentService.submit_payment_proof(
            session=session,
            user=user,
            proof_file_id=proof_file_id,
            amount=float(settings.FEG_REGISTRATION_FEE)
        )

        member_feg_id = user.feg_member_id
        fpl_id_str = str(fpl.fpl_id) if fpl else "N/A"
        manager_name = fpl.manager_name if fpl else "N/A"
        team_name = fpl.team_name if fpl else "N/A"
        payout_bank = payout.bank_name if payout else "N/A"
        payout_acc_name = payout.account_name if payout else "N/A"
        payout_acc_num = "N/A"
        if payout and payout.encrypted_account_number:
            try:
                payout_acc_num = decrypt_string(payout.encrypted_account_number)
            except Exception:
                payout_acc_num = payout.masked_account_number or "N/A"
        payment_id = payment.id

    msg = (
        "PAYMENT STATUS:\n"
        "🟡 **PENDING ADMIN REVIEW**\n\n"
        "Your payment proof has been submitted successfully.\n"
        "An FEG administrator will review your bank transfer receipt shortly.\n"
        "You will receive an automated Telegram notification with your community link as soon as approved!"
    )
    await safe_send_markdown(update.message, msg)

    # Notify Super Admin & Finance Admin in DM
    from services.auth_service import AuthService
    admin_ids = AuthService.get_payment_admin_ids()
    if not admin_ids:
        admin_ids = [update.effective_user.id]

    header_title = "🔄 **NEW MEMBERSHIP RENEWAL SUBMISSION** 🚨" if is_renewal else "💳 **NEW PAYMENT SUBMISSION FOR REVIEW** 🚨"
    approve_cb = f"approve_ren_{user.id}" if is_renewal else f"approve_pay_{payment_id}"
    reject_cb = f"reject_ren_{user.id}" if is_renewal else f"reject_pay_{payment_id}"

    admin_alert = (
        f"{header_title}\n\n"
        "👤 **MEMBER DETAILS:**\n"
        f"• **Full Name:** {user.full_name}\n"
        f"• **FEG Member ID:** `{member_feg_id}`\n"
        f"• **Telegram:** @{update.effective_user.username or 'NoUsername'} (`{telegram_id}`)\n"
        f"• **Membership Status:** `{user.membership_status}`\n\n"
        "⚽ **FPL DETAILS:**\n"
        f"• **FPL ID:** `{fpl_id_str}`\n"
        f"• **Manager:** {manager_name}\n"
        f"• **Team:** {team_name}\n\n"
        "🏦 **PAYOUT BANK DETAILS:**\n"
        f"• **Bank:** {payout_bank}\n"
        f"• **Account Name:** {payout_acc_name}\n"
        f"• **Account Number:** `{payout_acc_num}`\n\n"
        "💰 **PAYMENT DETAILS:**\n"
        f"• **Amount:** ₦{settings.FEG_REGISTRATION_FEE:,}\n"
        "• **Status:** 🟡 PENDING ADMIN RENEWAL REVIEW\n\n"
        "Click **APPROVE RENEWAL** to activate member for the new season, or **REJECT RENEWAL**."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ APPROVE RENEWAL" if is_renewal else "✅ APPROVE PAYMENT", callback_data=approve_cb),
            InlineKeyboardButton("❌ REJECT RENEWAL" if is_renewal else "❌ REJECT PAYMENT", callback_data=reject_cb)
        ]
    ])

    sent_count = 0
    for admin_id in set(admin_ids):
        if admin_id:
            try:
                if is_document:
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=proof_file_id,
                        caption=admin_alert,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=proof_file_id,
                        caption=admin_alert,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                sent_count += 1
                logger.info(f"Successfully sent payment review receipt alert to Admin Telegram ID {admin_id}")
            except Exception as media_err:
                logger.warning(f"Media alert with Markdown failed for Admin ID {admin_id}: {media_err}. Attempting plain media fallback...")
                try:
                    plain_alert = admin_alert.replace("**", "").replace("`", "")
                    if is_document:
                        await context.bot.send_document(
                            chat_id=admin_id,
                            document=proof_file_id,
                            caption=plain_alert,
                            reply_markup=keyboard
                        )
                    else:
                        await context.bot.send_photo(
                            chat_id=admin_id,
                            photo=proof_file_id,
                            caption=plain_alert,
                            reply_markup=keyboard
                        )
                    sent_count += 1
                    logger.info(f"Successfully sent plain media fallback receipt alert to Admin ID {admin_id}")
                except Exception as fallback_err:
                    logger.warning(f"Plain media failed for Admin ID {admin_id}: {fallback_err}. Sending separate receipt media + text message...")
                    try:
                        if is_document:
                            await context.bot.send_document(chat_id=admin_id, document=proof_file_id)
                        else:
                            await context.bot.send_photo(chat_id=admin_id, photo=proof_file_id)

                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=admin_alert,
                            reply_markup=keyboard,
                            parse_mode="Markdown"
                        )
                        sent_count += 1
                        logger.info(f"Successfully sent separate receipt media + details alert to Admin ID {admin_id}")
                    except Exception as final_err:
                        logger.error(f"Failed to deliver payment review DM to Admin ID {admin_id}: {final_err}")

    if sent_count == 0:
        logger.error(
            "⚠️ CRITICAL: Payment notification could not be delivered to any Admin DM! "
            "Please ensure Admin Telegram IDs are configured in .env and admins have pressed /start in DM with @FEGFPL_Bot."
        )

    return ConversationHandler.END


async def cancel_registration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Registration cancelled. You can type /start anytime to begin again.")
    return ConversationHandler.END


async def renew_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with get_db_session() as session:
        db_user = await MemberService.get_user_by_telegram_id(session, user.id)
        pay_cfg = await get_latest_active_payment_account(session)
        bank_name = pay_cfg.bank_name if pay_cfg else settings.FEG_PAYMENT_BANK
        account_name = pay_cfg.account_name if pay_cfg else settings.FEG_PAYMENT_ACCOUNT_NAME
        account_number = pay_cfg.account_number if pay_cfg else settings.FEG_PAYMENT_ACCOUNT_NUMBER

    from services.season_reminder_service import SeasonReminderService
    dates = await SeasonReminderService.get_season_dates()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    in_renewal_window = dates["reminder_start_dt"] <= now_utc <= dates["gw1_deadline_dt"]

    # If member is ACTIVE and NOT in season renewal window, inform them nicely
    if db_user and db_user.membership_status == "ACTIVE" and not in_renewal_window and db_user.renewal_payment_status != "PENDING_APPROVAL":
        msg = (
            "🟢 **YOUR MEMBERSHIP IS CURRENTLY ACTIVE** ⚽\n\n"
            f"Hi **{db_user.full_name}**! Your FEG FPL membership for the **{db_user.current_season or '2026/2027'}** season is fully active.\n\n"
            "ℹ️ **Season Renewal Notice:**\n"
            "Annual membership renewals for the upcoming season officially open **5 weeks prior to the start of each new Premier League season** (3 weeks before the purge deadline, based on the official FPL API).\n\n"
            "📢 The bot will automatically send you a direct message when the renewal window for the next season opens!"
        )
        await safe_send_markdown(update.message, msg)
        return ConversationHandler.END

    context.user_data["is_renewal"] = True

    msg = (
        "🔄 **FEG SEASON MEMBERSHIP RENEWAL**\n\n"
        f"To renew your FEG FPL membership for the **{db_user.current_season if db_user else 'upcoming'}** season, "
        f"please transfer the annual fee of **₦{settings.FEG_REGISTRATION_FEE:,}** to:\n\n"
        f"🏦 **Bank:** {bank_name}\n"
        f"👤 **Account Name:** {account_name}\n"
        f"🔢 **Account Number:** `{account_number}`\n\n"
        "📸 Please upload a screenshot or document receipt of your payment transfer below:"
    )
    await safe_send_markdown(update.message, msg)
    return PAYMENT_PROOF


def get_registration_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_registration_callback, pattern="^start_registration$"),
            CommandHandler("register", start_registration_callback),
            CommandHandler("renew", renew_command_handler),
            CommandHandler("pay", show_payment_details_handler),
            CommandHandler("payment", show_payment_details_handler)
        ],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_handler)],
            FPL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, fpl_id_handler)],
            BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bank_name_handler)],
            ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_name_handler)],
            ACCOUNT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, account_number_handler)],
            VERIFY_DETAILS: [
                CallbackQueryHandler(confirm_details_callback, pattern="^confirm_details$"),
                CallbackQueryHandler(edit_full_name_callback, pattern="^edit_full_name$"),
                CallbackQueryHandler(edit_fpl_id_callback, pattern="^edit_fpl_id$"),
                CallbackQueryHandler(edit_bank_details_callback, pattern="^edit_bank_details$")
            ],
            PAYMENT_PROOF: [MessageHandler(filters.PHOTO | filters.Document.ALL, payment_proof_handler)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_registration_handler),
            CallbackQueryHandler(help_fpl_id_callback, pattern="^help_fpl_id$")
        ]
    )
