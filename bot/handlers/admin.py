import datetime
import io
import csv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_db_session
from database.models import User, FPLProfile, PayoutAccount, Payment, Referral, Reward, AuditLog
from database.repository import (
    get_latest_active_payment_account,
    create_payment_account_config,
    add_audit_log
)
from services.auth_service import admin_required
from services.fpl_service import FPLService
from services.referral_service import ReferralService
from services.reward_service import RewardService
from database.crypto import decrypt_string
from config.settings import settings
from config.logging_config import logger
from sqlalchemy import select, func, text


async def safe_reply(target_msg, text: str, reply_markup=None, disable_web_page_preview=False):
    try:
        await target_msg.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=disable_web_page_preview
        )
    except Exception as err:
        logger.warning(f"Markdown parse error in admin handler: {err}. Falling back to plain text rendering.")
        plain_text = text.replace("**", "").replace("`", "")
        await target_msg.reply_text(
            text=plain_text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )


@admin_required()
async def admin_dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_role = getattr(context, "user_role", "SUPER_ADMIN")

    async with get_db_session() as session:
        stmt_tot = select(func.count(User.id))
        total_users = (await session.execute(stmt_tot)).scalar() or 0

        stmt_act = select(func.count(User.id)).where(User.registration_status.in_(["APPROVED", "COMMUNITY_ACCESS_GRANTED"]))
        active_count = (await session.execute(stmt_act)).scalar() or 0

        stmt_pend = select(func.count(Payment.id)).where(Payment.payment_status == "PENDING")
        pending_count = (await session.execute(stmt_pend)).scalar() or 0

        stmt_rew = select(func.sum(Reward.amount)).where(Reward.status == "PAID")
        total_rewards_paid = (await session.execute(stmt_rew)).scalar() or 0.0

        stmt_audit_cnt = select(func.count(AuditLog.id))
        total_audits = (await session.execute(stmt_audit_cnt)).scalar() or 0

    def get_super_admin_keyboard():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💳 REVIEW PAYMENTS ({pending_count})", callback_data="admin_payments"), InlineKeyboardButton(f"👥 MEMBERS ({active_count}/{total_users})", callback_data="admin_members")],
            [InlineKeyboardButton("📋 TEAM AUDIT LOGS", callback_data="admin_audit_logs"), InlineKeyboardButton("📊 REFERRALS TRACKER", callback_data="admin_referrals")],
            [InlineKeyboardButton("⚽ FPL ENGINE", callback_data="admin_fpl_engine"), InlineKeyboardButton("🔴 LIVE MATCH ENGINE", callback_data="admin_live_engine")],
            [InlineKeyboardButton("📈 STATISTICS ENGINE", callback_data="admin_stats_engine"), InlineKeyboardButton("📰 CONTENT ENGINE", callback_data="admin_content_engine")],
            [InlineKeyboardButton("🟢 SYSTEM HEALTH", callback_data="admin_sys_health"), InlineKeyboardButton("⚙️ SETTINGS & CONFIG", callback_data="admin_settings")],
            [InlineKeyboardButton("🔄 REFRESH MASTER DASHBOARD", callback_data="admin_refresh")]
        ])

    def get_finance_admin_keyboard():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💳 PENDING PAYMENTS ({pending_count})", callback_data="admin_payments")],
            [InlineKeyboardButton(f"👥 MEMBERS DIRECTORY ({active_count})", callback_data="admin_members"), InlineKeyboardButton("📊 REFERRAL REWARDS", callback_data="admin_referrals")]
        ])

    def get_content_admin_keyboard():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"👥 MEMBERS DIRECTORY ({active_count})", callback_data="admin_members")]
        ])

    if admin_role == "SUPER_ADMIN":
        msg = (
            "👑 **FEG SUPER ADMIN MASTER CONTROL DASHBOARD** 🛡️\n\n"
            "📊 **COMMUNITY OVERVIEW & METRICS:**\n"
            f"• **Total Registered Users:** `{total_users}`\n"
            f"• **Verified Active Paid Members:** `{active_count}`\n"
            f"• **Pending Payment Proofs:** `{pending_count}`\n"
            f"• **Total Rewards Disbursed:** ₦{total_rewards_paid:,.0f}\n\n"
            "👥 **TEAM MEMBERS & AUDIT TRAIL:**\n"
            f"• **Team Audit Logs Recorded:** `{total_audits}` actions\n"
            "• **Active Admin Roles:** Super Admin, Finance Admin, Content Admin\n\n"
            "⚙️ **SYSTEM ENGINES & MODULES:**\n"
            "• ⚽ **FPL Engine** — Live API sync & Gameweek deadlines\n"
            "• 🔴 **Live Match Engine** — Live scoring feed & GW tracking\n"
            "• 📈 **Statistics Engine** — Player form, ownership & price analytics\n"
            "• 📰 **Content Engine** — Media, captain picks & graphics generator\n"
            "• 🟢 **System Health** — Bot core, DB & encryption security\n"
            "• ⚙️ **Settings & Config** — Receiving bank config & fee settings\n\n"
            "🛠️ **MASTER CONTROL COMMANDS DIRECTORY:**\n"
            "• `/audit_logs` — Track team duties & administrative audit trail\n"
            "• `/pending` or `/payments` — Review pending member payment proofs\n"
            "• `/members` — Browse active member directory & payout bank details\n"
            "• `/search_member [NAME/ID]` — Search member by Name, FEG ID, Username, or FPL ID\n"
            "• `/admin_referrals` — Track referral milestone leaderboard & payouts\n"
            "• `/set_pay_account` — Update receiving bank account details\n"
            "• `/finalizeseason` — Trigger automated FPL season wrap & Hall of Fame\n"
            "• `/announce_gw_winner` — Post Gameweek winner & alert Finance Admin\n\n"
            "Select an administrative management module below:"
        )
        keyboard = get_super_admin_keyboard()
    elif admin_role == "FINANCE_ADMIN":
        msg = (
            "💰 **FEG FINANCE ADMIN DASHBOARD**\n\n"
            f"📥 **Pending Payments to Review:** `{pending_count}`\n"
            f"👥 **Verified Active Members:** `{active_count}`\n\n"
            "Welcome, Finance Administrator. Use buttons below or `/pending` to review payment submissions, "
            "approve access, and process reward payouts."
        )
        keyboard = get_finance_admin_keyboard()
    elif admin_role == "CONTENT_ADMIN":
        msg = (
            "📰 **FEG CONTENT ADMIN DASHBOARD**\n\n"
            f"👥 **Verified Community Members:** `{active_count}`\n"
            f"📥 **Pending Payments to Review:** `{pending_count}`\n\n"
            "Welcome, Content Administrator. Your role covers FPL content generation, "
            "gameweek previews/reviews, player stats, live match engine, and Team of the GW graphics."
        )
        keyboard = get_content_admin_keyboard()
    else:
        msg = "⚠️ Unrecognized admin role."
        keyboard = None

    target_msg = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()

    await safe_reply(target_msg, msg, reply_markup=keyboard)


@admin_required("SUPER_ADMIN")
async def admin_audit_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.callback_query.message if update.callback_query else update.message

    async with get_db_session() as session:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(15)
        res = await session.execute(stmt)
        logs = res.scalars().all()

        if not logs:
            await safe_reply(target_msg, "📋 **FEG TEAM AUDIT TRAIL & DUTIES**\n\nNo administrative audit logs recorded yet.")
            return

        lines = ["📋 **FEG TEAM AUDIT TRAIL & DUTIES LOG**\n"]
        for idx, log in enumerate(logs, 1):
            time_str = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(
                f"{idx}. `[{time_str}]` **{log.role}** (ID: `{log.admin_id}`)\n"
                f"   • **Action:** `{log.action}`\n"
                f"   • **Target:** `{log.target or 'N/A'}`\n"
                f"   • **Details:** {log.details or 'N/A'}\n"
                "───────────────────────────"
            )

        msg = "\n".join(lines)
        await safe_reply(target_msg, msg)


@admin_required()
async def admin_members_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.callback_query.message if update.callback_query else update.message

    async with get_db_session() as session:
        stmt_total = select(func.count(User.id))
        total_users = (await session.execute(stmt_total)).scalar() or 0

        stmt_active = select(func.count(User.id)).where(User.registration_status.in_(["APPROVED", "COMMUNITY_ACCESS_GRANTED"]))
        active_users = (await session.execute(stmt_active)).scalar() or 0

        stmt_pending = select(func.count(User.id)).where(User.registration_status == "PENDING_PAYMENT_PROOF")
        pending_users = (await session.execute(stmt_pending)).scalar() or 0

        stmt_users = select(User).order_by(User.created_at.desc()).limit(15)
        res = await session.execute(stmt_users)
        users = res.scalars().all()

        if not users:
            await safe_reply(target_msg, "👥 **FEG MEMBERS DIRECTORY**\n\nNo members registered in database.")
            return

        summary_text = (
            "👥 **FEG MEMBERS DIRECTORY & METRICS**\n\n"
            f"• **Total Database Registrations:** `{total_users}`\n"
            f"• **Verified Active Community Members:** `{active_users}`\n"
            f"• **Pending Payment Proofs:** `{pending_users}`\n\n"
            "Click any member below to inspect their full profile & payout bank details:"
        )

        buttons = []
        for u in users:
            status_tag = f"[{u.registration_status}]"
            btn_text = f"👤 {u.full_name} ({u.feg_member_id}) - {status_tag}"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"view_member_{u.id}")])

        keyboard = InlineKeyboardMarkup(buttons)
        await safe_reply(target_msg, summary_text, reply_markup=keyboard)


@admin_required()
async def search_member_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    target_msg = update.callback_query.message if update.callback_query else update.message

    if not args:
        await safe_reply(
            target_msg,
            "🔍 **SEARCH MEMBER DIRECTORY**\n\n"
            "Usage: `/search_member [NAME / FEG_ID / TELEGRAM_ID / USERNAME / FPL_ID]`\n\n"
            "Examples:\n"
            "• `/search_member Emmanuel`\n"
            "• `/search_member FEG-2026-0001`\n"
            "• `/search_member @username`\n"
            "• `/search_member 12345678`"
        )
        return

    query_str = " ".join(args).strip()

    async with get_db_session() as session:
        stmt = select(User).where(
            (User.feg_member_id.ilike(f"%{query_str}%")) |
            (User.full_name.ilike(f"%{query_str}%")) |
            (User.telegram_username.ilike(f"%{query_str.replace('@', '')}%"))
        )
        if query_str.isdigit():
            stmt = select(User).where((User.telegram_id == int(query_str)) | (User.id == int(query_str)))

        res = await session.execute(stmt)
        users = res.scalars().all()

        if not users and query_str.isdigit():
            stmt_fpl = select(FPLProfile).where(FPLProfile.fpl_id == int(query_str))
            fpl_res = (await session.execute(stmt_fpl)).scalar_one_or_none()
            if fpl_res:
                stmt_u = select(User).where(User.id == fpl_res.user_id)
                users = (await session.execute(stmt_u)).scalars().all()

        if not users:
            await safe_reply(target_msg, f"🔍 No registered member found matching `{query_str}`.")
            return

        if len(users) == 1:
            await render_full_member_profile(update, context, session, users[0])
        else:
            buttons = []
            for u in users:
                btn_text = f"👤 {u.full_name} ({u.feg_member_id})"
                buttons.append([InlineKeyboardButton(btn_text, callback_data=f"view_member_{u.id}")])
            keyboard = InlineKeyboardMarkup(buttons)
            await safe_reply(target_msg, f"🔍 **FOUND {len(users)} MEMBERS MATCHING '{query_str}':**", reply_markup=keyboard)


@admin_required()
async def view_member_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.data.replace("view_member_", "")

    async with get_db_session() as session:
        stmt = select(User).where(User.id == int(user_id))
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            await query.message.reply_text("⚠️ User record not found.", parse_mode="Markdown")
            return

        await render_full_member_profile(update, context, session, user)


async def render_full_member_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, session, user: User):
    target_msg = update.callback_query.message if update.callback_query else update.message

    stmt_fpl = select(FPLProfile).where(FPLProfile.user_id == user.id)
    fpl = (await session.execute(stmt_fpl)).scalar_one_or_none()

    stmt_payout = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
    payout = (await session.execute(stmt_payout)).scalar_one_or_none()

    decrypted_acc_num = "Not set"
    if payout and payout.encrypted_account_number:
        try:
            decrypted_acc_num = decrypt_string(payout.encrypted_account_number)
        except Exception:
            decrypted_acc_num = payout.masked_account_number or "Not set"

    stmt_ref = select(func.count(Referral.id)).where(Referral.referrer_user_id == user.id)
    ref_count = (await session.execute(stmt_ref)).scalar() or 0

    msg = (
        "👤 **FULL MEMBER ADMINISTRATIVE PROFILE**\n\n"
        f"• **Full Name:** {user.full_name}\n"
        f"• **FEG Member ID:** `{user.feg_member_id}`\n"
        f"• **Registration Status:** `{user.registration_status}`\n"
        f"• **Telegram ID:** `{user.telegram_id}` (@{user.telegram_username or 'NoUsername'})\n"
        f"• **Joined Date:** {user.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
        "⚽ **FPL DETAILS:**\n"
        f"• **FPL ID:** `{fpl.fpl_id if fpl else 'N/A'}`\n"
        f"• **Manager:** {fpl.manager_name if fpl else 'N/A'}\n"
        f"• **Team:** {fpl.team_name if fpl else 'N/A'}\n\n"
        "🏦 **PAYOUT BANK DETAILS (FOR PRIZE DISBURSEMENT):**\n"
        f"• **Bank:** {payout.bank_name if payout else 'N/A'}\n"
        f"• **Account Name:** {payout.account_name if payout else 'N/A'}\n"
        f"• **Decrypted Account Number:** `{decrypted_acc_num}`\n\n"
        "👥 **REFERRALS:**\n"
        f"• **Referral Code:** `{user.referral_code}`\n"
        f"• **Total Referred Members:** `{ref_count}`"
    )

    await safe_reply(target_msg, msg)


@admin_required("SUPER_ADMIN", "FINANCE_ADMIN")
async def admin_update_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("/admin_update_member", "").replace("/update_member", "").strip()
    parts = [p.strip() for p in text.split("|") if p.strip()]

    if len(parts) != 6:
        await safe_reply(
            update.message,
            "⚠️ **INVALID FORMAT**\n\n"
            "Usage: `/admin_update_member TelegramID_or_MemberID | Full Name | FPL ID | Bank Name | Account Name | Account Number`\n\n"
            "Example:\n`/admin_update_member 6948840492 | Odeyemi Omogbolahan | 672262 | Palmpay | Odeyemi Omogbolahan | 8066106785`"
        )
        return

    target_id, full_name, fpl_id_str, bank_name, account_name, account_number = parts

    async with get_db_session() as session:
        user = None
        if target_id.isdigit():
            user = await MemberService.get_user_by_telegram_id(session, int(target_id))
        if not user:
            stmt = select(User).where(User.feg_member_id == target_id)
            user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            await safe_reply(update.message, f"❌ Member '{target_id}' not found in database.")
            return

        user.full_name = full_name
        user.registration_status = "COMMUNITY_ACCESS_GRANTED"

        if fpl_id_str.isdigit():
            fpl_id = int(fpl_id_str)
            mgr, team = await FPLService.get_user_fpl_details(fpl_id)
            stmt_f = select(FPLProfile).where(FPLProfile.user_id == user.id)
            fpl = (await session.execute(stmt_f)).scalar_one_or_none()

            is_classic = await FPLService.check_league_membership(settings.FPL_CLASSIC_LEAGUE_ID, fpl_id, "classic")
            is_h2h = await FPLService.check_league_membership(settings.FPL_H2H_LEAGUE_ID, fpl_id, "h2h")

            if not fpl:
                fpl = FPLProfile(
                    user_id=user.id,
                    fpl_id=fpl_id,
                    manager_name=mgr or full_name,
                    team_name=team or "FEG FC",
                    classic_status="VERIFIED" if is_classic else "PENDING",
                    h2h_status="VERIFIED" if is_h2h else "PENDING"
                )
                session.add(fpl)
            else:
                fpl.fpl_id = fpl_id
                fpl.manager_name = mgr or full_name
                fpl.team_name = team or "FEG FC"
                fpl.classic_status = "VERIFIED" if is_classic else "PENDING"
                fpl.h2h_status = "VERIFIED" if is_h2h else "PENDING"

        stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        payout = (await session.execute(stmt_p)).scalar_one_or_none()
        enc_num = encrypt_string(account_number)
        masked_num = mask_account_number(account_number)

        if not payout:
            payout = PayoutAccount(
                user_id=user.id,
                bank_name=bank_name,
                account_name=account_name,
                encrypted_account_number=enc_num,
                masked_account_number=masked_num
            )
            session.add(payout)
        else:
            payout.bank_name = bank_name
            payout.account_name = account_name
            payout.encrypted_account_number = enc_num
            payout.masked_account_number = masked_num

        await session.commit()
        from services.backup_service import BackupService
        await BackupService.backup_all_members_to_json()

        await safe_reply(
            update.message,
            f"✅ **MEMBER PROFILE UPDATED BY ADMIN!**\n\n"
            f"• **Member:** {escape_markdown(user.full_name)} (`{user.feg_member_id}`)\n"
            f"• **FPL ID:** `{fpl_id_str}`\n"
            f"• **Bank:** {escape_markdown(bank_name)} / {escape_markdown(account_name)} / `{masked_num}`"
        )


async def admin_update_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("/update_account", "").replace("/update_bank", "").strip()
    parts = text.split()

    if len(parts) < 2:
        await safe_reply(
            update.message,
            "⚠️ **USAGE:**\n`/update_account <MemberID_or_TelegramID> <Account_Number> [Bank_Name] [Account_Name]`\n\n"
            "**Examples:**\n"
            "• `/update_account FEG-2026-000001 8066106785`\n"
            "• `/update_account 6948840492 8066106785 Opay \"Ilesanmi Emmanuel Eniola\"`"
        )
        return

    target_id = parts[0].strip()
    acc_num = parts[1].strip()
    bank_name = parts[2].strip() if len(parts) > 2 else None
    acc_name = " ".join(parts[3:]).strip() if len(parts) > 3 else None

    async with get_db_session() as session:
        user = None
        if target_id.isdigit():
            user = await MemberService.get_user_by_telegram_id(session, int(target_id))
        if not user:
            stmt = select(User).where(User.feg_member_id == target_id.upper())
            user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            await safe_reply(update.message, f"❌ Member '{target_id}' not found in database.")
            return

        stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        payout = (await session.execute(stmt_p)).scalar_one_or_none()

        enc_num = encrypt_string(acc_num)
        masked_num = mask_account_number(acc_num)
        b_name = bank_name or (payout.bank_name if payout else "Palmpay")
        a_name = acc_name or (payout.account_name if payout else user.full_name)

        if not payout:
            payout = PayoutAccount(
                user_id=user.id,
                bank_name=b_name,
                account_name=a_name,
                encrypted_account_number=enc_num,
                masked_account_number=masked_num
            )
            session.add(payout)
        else:
            payout.bank_name = b_name
            payout.account_name = a_name
            payout.encrypted_account_number = enc_num
            payout.masked_account_number = masked_num

        await session.commit()

        # Update JSON file backup
        from services.backup_service import BackupService
        await BackupService.backup_all_members_to_json()

        full_dec = decrypt_string(payout.encrypted_account_number)

        await safe_reply(
            update.message,
            f"✅ **MEMBER BANK ACCOUNT UPDATED!**\n\n"
            f"• **Member:** {escape_markdown(user.full_name)} (`{user.feg_member_id}`)\n"
            f"• **Telegram ID:** `{user.telegram_id}` (@{user.telegram_username or 'NoUsername'})\n"
            f"• **Bank Name:** {escape_markdown(payout.bank_name)}\n"
            f"• **Account Name:** {escape_markdown(payout.account_name)}\n"
            f"• **Full Decrypted Account Number (Admin View):** `{full_dec}`\n"
            f"• **Masked Account Number (Member View):** `{payout.masked_account_number}`"
        )


@admin_required("SUPER_ADMIN", "FINANCE_ADMIN")
async def export_members_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.callback_query.message if update.callback_query else update.message
    await safe_reply(target_msg, "📊 **GENERATING FULL FEG MEMBER DATABASE EXPORT (CSV)...**")

    async with get_db_session() as session:
        stmt = select(User).order_by(User.id.asc())
        res = await session.execute(stmt)
        users = res.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "FEG Member ID", "Full Name", "Telegram ID", "Telegram Username",
            "Registration Status", "Membership Status", "FPL ID", "Manager Name", "Team Name",
            "Classic Status", "H2H Status", "Bank Name", "Account Name",
            "Decrypted Account Number", "Referral Code", "Invites Count", "Joined Date"
        ])

        for u in users:
            stmt_f = select(FPLProfile).where(FPLProfile.user_id == u.id)
            fpl = (await session.execute(stmt_f)).scalar_one_or_none()

            stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == u.id)
            payout = (await session.execute(stmt_p)).scalar_one_or_none()

            dec_num = "N/A"
            if payout and payout.encrypted_account_number:
                try:
                    dec_num = decrypt_string(payout.encrypted_account_number)
                except Exception:
                    dec_num = payout.masked_account_number or "N/A"

            stmt_ref = select(func.count(Referral.id)).where(Referral.referrer_user_id == u.id)
            ref_count = (await session.execute(stmt_ref)).scalar() or 0

            writer.writerow([
                u.feg_member_id,
                u.full_name,
                u.telegram_id,
                u.telegram_username or "N/A",
                u.registration_status,
                u.membership_status,
                fpl.fpl_id if fpl else "N/A",
                fpl.manager_name if fpl else "N/A",
                fpl.team_name if fpl else "N/A",
                fpl.classic_status if fpl else "N/A",
                fpl.h2h_status if fpl else "N/A",
                payout.bank_name if payout else "N/A",
                payout.account_name if payout else "N/A",
                dec_num,
                u.referral_code,
                ref_count,
                u.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])

        csv_bytes = output.getvalue().encode("utf-8")
        bio = io.BytesIO(csv_bytes)
        bio.name = "feg_members_database_export.csv"

        await context.bot.send_document(
            chat_id=target_msg.chat_id,
            document=bio,
            filename="feg_members_database_export.csv",
            caption=f"📊 **FEG MEMBER DATABASE EXPORT COMPLETE**\nTotal Members Exported: `{len(users)}`"
        )


@admin_required("SUPER_ADMIN")
async def admin_start_new_season_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.replace("/start_new_season", "").strip()
    new_season = text_input if text_input else "2027/2028"

    # Calculate deadline 14 days before FPL GW1 official start date
    import datetime
    from services.fpl_service import FPLService
    gw1_info = await FPLService.get_gameweek_info(1)

    deadline_dt = None
    if gw1_info and gw1_info.get("deadline_time"):
        try:
            dl_str = gw1_info["deadline_time"].replace("Z", "+00:00")
            gw1_dt = datetime.datetime.fromisoformat(dl_str)
            deadline_dt = gw1_dt - datetime.timedelta(days=14)
        except Exception as e:
            logger.warning(f"Could not parse GW1 deadline: {e}")

    if not deadline_dt:
        # Default fallback: August 1st of the starting year
        year = int(new_season.split("/")[0]) if "/" in new_season else 2027
        deadline_dt = datetime.datetime(year, 8, 1, 23, 59, 59, tzinfo=datetime.timezone.utc)

    async with get_db_session() as session:
        stmt = select(User).where(User.membership_status == "ACTIVE")
        users = (await session.execute(stmt)).scalars().all()

        updated_count = 0
        for u in users:
            u.membership_status = "PENDING_RENEWAL"
            u.renewal_payment_status = "NOT_SUBMITTED"
            u.renewal_deadline = deadline_dt
            u.current_season = new_season
            updated_count += 1

        await session.commit()

    from services.backup_service import BackupService
    await BackupService.backup_all_members_to_json()

    deadline_fmt = deadline_dt.strftime("%Y-%m-%d %H:%M UTC")

    msg = (
        "🚀 **NEW SEASON INITIALIZED** ⚽\n\n"
        f"• **New Season:** `{new_season}`\n"
        f"• **Members Set to PENDING_RENEWAL:** `{updated_count}`\n"
        f"• **Official Renewal Deadline (14 days before GW1):** `{deadline_fmt}`\n\n"
        "💡 *Active members are now prompted to use /renew to submit their annual renewal proof.*"
    )
    await safe_reply(update.message, msg)


@admin_required("SUPER_ADMIN")
async def admin_purge_unrenewed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with get_db_session() as session:
        stmt = select(User).where(User.membership_status == "PENDING_RENEWAL")
        pending_users = (await session.execute(stmt)).scalars().all()

    if not pending_users:
        await safe_reply(update.message, "✅ No members are currently pending renewal for purge.")
        return

    preview_lines = [f"• `{u.feg_member_id}` - {u.full_name} (@{u.telegram_username or 'NoUsername'})" for u in pending_users[:15]]
    more_count = len(pending_users) - 15 if len(pending_users) > 15 else 0

    msg = (
        "⚠️ **CONFIRM PURGE UNRENEWED MEMBERS** 🚨\n\n"
        f"Found **{len(pending_users)}** member(s) with `PENDING_RENEWAL` status.\n\n"
        "**Unrenewed Members Preview:**\n" + "\n".join(preview_lines) +
        (f"\n*...and {more_count} more members*" if more_count > 0 else "") +
        "\n\nPurging will soft-delete these members to `EXPIRED` status. Their historical points and Hall of Fame records will be preserved permanently."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ CONFIRM PURGE UNRENEWED MEMBERS", callback_data="confirm_purge_unrenewed")],
        [InlineKeyboardButton("❌ CANCEL PURGE", callback_data="cancel_purge_unrenewed")]
    ])
    await safe_reply(update.message, msg, reply_markup=keyboard)


@admin_required("SUPER_ADMIN")
async def admin_confirm_purge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_purge_unrenewed":
        await query.message.edit_text("❌ Purge unrenewed members cancelled.")
        return

    async with get_db_session() as session:
        stmt = select(User).where(User.membership_status == "PENDING_RENEWAL")
        pending_users = (await session.execute(stmt)).scalars().all()

        purged_count = 0
        for u in pending_users:
            u.membership_status = "EXPIRED"
            purged_count += 1

        await session.commit()

    from services.backup_service import BackupService
    await BackupService.backup_all_members_to_json()

    await query.message.edit_text(
        f"⚠️ **PURGE UNRENEWED MEMBERS COMPLETE**\n\n"
        f"• **Total Members Soft-Deleted to EXPIRED:** `{purged_count}`\n"
        f"• **Historical Records & Hall of Fame Data:** Preserved\n"
        "• **JSON Backup Snapshot:** Updated"
    )


@admin_required("SUPER_ADMIN", "CONTENT_ADMIN")
async def admin_record_hall_of_fame_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.replace("/record_hall_of_fame", "").replace("/add_hof", "").strip()
    parts = [p.strip() for p in text_input.split("|")]

    if len(parts) < 5:
        await safe_reply(
            update.message,
            "⚠️ **USAGE:**\n`/record_hall_of_fame Season | Category | FEG_Member_ID | Rank | Title | [Details]`\n\n"
            "**Example:**\n"
            "`/record_hall_of_fame 2026/2027 | CLASSIC | FEG-2026-000001 | 1 | Classic Champion`"
        )
        return

    season_str, category_str, target_id, rank_str, title_str = parts[:5]
    details_str = parts[5] if len(parts) > 5 else None
    rank_int = int(rank_str) if rank_str.isdigit() else 1

    async with get_db_session() as session:
        stmt_u = select(User).where(User.feg_member_id == target_id.upper())
        user = (await session.execute(stmt_u)).scalar_one_or_none()

        if not user:
            stmt_t = select(User).where(User.telegram_id == (int(target_id) if target_id.isdigit() else 0))
            user = (await session.execute(stmt_t)).scalar_one_or_none()

        mgr_name = user.full_name if user else f"Manager {target_id}"
        team_name = "FEG FC"

        if user:
            stmt_f = select(FPLProfile).where(FPLProfile.user_id == user.id)
            fpl = (await session.execute(stmt_f)).scalar_one_or_none()
            if fpl:
                mgr_name = fpl.manager_name or mgr_name
                team_name = fpl.team_name or team_name

        from database.models import HallOfFameRecord
        record = HallOfFameRecord(
            feg_member_id=user.feg_member_id if user else target_id,
            season=season_str,
            category=category_str.upper(),
            rank=rank_int,
            manager_name=mgr_name,
            team_name=team_name,
            title=title_str,
            details=details_str
        )
        session.add(record)
        await session.commit()

    msg = (
        "🏆 **PERMANENT HALL OF FAME RECORD ADDED!** 👑\n\n"
        f"• **Season:** `{season_str}`\n"
        f"• **Category:** `{category_str.upper()}` (Rank #{rank_int})\n"
        f"• **Member:** {mgr_name} (`{target_id}`)\n"
        f"• **Title:** {title_str}\n\n"
        "💡 *This record is permanent and will never be altered, even if members expire or leave.*"
    )
    await safe_reply(update.message, msg)


@admin_required("SUPER_ADMIN")
async def admin_trigger_renewal_reminders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update.message, "⏳ **CHECKING & SENDING AUTOMATED SEASON RENEWAL DM REMINDERS...**")
    from services.season_reminder_service import SeasonReminderService
    res = await SeasonReminderService.run_renewal_reminder_check(bot=context.bot, force=True)

    msg = (
        "📢 **SEASON RENEWAL REMINDERS SENT!** 📬\n\n"
        f"• **Status:** `{res.get('status')}`\n"
        f"• **Total Renewal DM Reminders Delivered:** `{res.get('sent_count', 0)}`\n"
        f"• **Purge Deadline Date:** `{res.get('purge_deadline')}`"
    )
    await safe_reply(update.message, msg)

    async with get_db_session() as session:
        stmt = select(User).order_by(User.id.asc())
        res = await session.execute(stmt)
        users = res.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "FEG Member ID", "Full Name", "Telegram ID", "Telegram Username",
            "Registration Status", "FPL ID", "Manager Name", "Team Name",
            "Classic Status", "H2H Status", "Bank Name", "Account Name",
            "Decrypted Account Number", "Referral Code", "Invites Count", "Joined Date"
        ])

        for u in users:
            stmt_f = select(FPLProfile).where(FPLProfile.user_id == u.id)
            fpl = (await session.execute(stmt_f)).scalar_one_or_none()

            stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == u.id)
            payout = (await session.execute(stmt_p)).scalar_one_or_none()

            dec_num = "N/A"
            if payout and payout.encrypted_account_number:
                try:
                    dec_num = decrypt_string(payout.encrypted_account_number)
                except Exception:
                    dec_num = payout.masked_account_number or "N/A"

            stmt_ref = select(func.count(Referral.id)).where(Referral.referrer_user_id == u.id)
            ref_count = (await session.execute(stmt_ref)).scalar() or 0

            writer.writerow([
                u.feg_member_id,
                u.full_name,
                u.telegram_id,
                u.telegram_username or "N/A",
                u.registration_status,
                fpl.fpl_id if fpl else "N/A",
                fpl.manager_name if fpl else "N/A",
                fpl.team_name if fpl else "N/A",
                fpl.classic_status if fpl else "N/A",
                fpl.h2h_status if fpl else "N/A",
                payout.bank_name if payout else "N/A",
                payout.account_name if payout else "N/A",
                dec_num,
                u.referral_code,
                ref_count,
                u.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])

        csv_bytes = output.getvalue().encode("utf-8")
        bio = io.BytesIO(csv_bytes)
        bio.name = "feg_members_database_export.csv"

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=bio,
            filename="feg_members_database_export.csv",
            caption=f"📊 **FEG MEMBER DATABASE EXPORT COMPLETE**\nTotal Members Exported: `{len(users)}`"
        )


async def admin_import_forwarded_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    text = msg.text or msg.caption or ""
    target_msg = msg
    if msg.reply_to_message:
        text = msg.reply_to_message.text or msg.reply_to_message.caption or text
        target_msg = msg.reply_to_message

    if not text or text.startswith("/"):
        return

    # Check if text contains member registration or profile card patterns
    has_member_card = any(k in text for k in ["MEMBER DETAILS", "Full Name:", "FEG Member ID", "Telegram:", "Telegram ID:", "FPL DETAILS", "FPL ID:", "PAYOUT BANK DETAILS", "Bank:"])
    if not has_member_card:
        return

    await process_and_restore_member_from_text(msg, target_msg, text)


async def restore_member_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    target_msg = msg.reply_to_message if msg.reply_to_message else msg
    text = target_msg.text or target_msg.caption or ""
    cmd_text = msg.text.replace("/restore_member", "").replace("/restore_profile", "").strip()
    if cmd_text:
        text = cmd_text

    if not text:
        await safe_reply(
            msg,
            "⚠️ **USAGE:** Reply to any message containing member details with `/restore_member` or paste the member text after `/restore_member <pasted_text>`."
        )
        return

    await process_and_restore_member_from_text(msg, target_msg, text)


async def process_and_restore_member_from_text(msg, target_msg, text: str):
    logger.info(f"Admin parsing member text (len={len(text)})...")

    tg_id_match = (
        re.search(r"Telegram:\s*@?[a-zA-Z0-9_]*\s*\(?`?(\d{6,11})`?\)?", text, re.IGNORECASE) or
        re.search(r"Telegram ID:\s*`?(\d{6,11})`?", text, re.IGNORECASE) or
        re.search(r"User ID:\s*`?(\d{6,11})`?", text, re.IGNORECASE) or
        re.search(r"ID:\s*`?(\d{6,11})`?", text, re.IGNORECASE) or
        re.search(r"\(`?(\d{6,11})`?\)", text) or
        re.search(r"(\d{9,11})", text)
    )
    feg_id_match = re.search(r"FEG-202\d-\d{6}", text, re.IGNORECASE)
    username_match = re.search(r"@([a-zA-Z0-9_]{4,32})", text)
    name_match = (
        re.search(r"Full Name:\s*([^\n\•\*\`]+)", text, re.IGNORECASE) or
        re.search(r"Member Name:\s*([^\n\•\*\`]+)", text, re.IGNORECASE) or
        re.search(r"Member:\s*([^\n\•\*\`]+)", text, re.IGNORECASE) or
        re.search(r"Manager:\s*([^\n\•\*\`]+)", text, re.IGNORECASE)
    )
    fpl_id_match = (
        re.search(r"FPL ID:\s*`?(\d{4,9})`?", text, re.IGNORECASE) or
        re.search(r"FPL:\s*`?(\d{4,9})`?", text, re.IGNORECASE)
    )
    bank_match = re.search(r"Bank:\s*([^\n\•\*\`]+)", text, re.IGNORECASE)
    acc_name_match = re.search(r"Account Name:\s*([^\n\•\*\`]+)", text, re.IGNORECASE)
    acc_num_match = re.search(r"Account Number:\s*`?(\d{8,11})`?", text, re.IGNORECASE)

    tid = None
    if tg_id_match:
        tid = int(tg_id_match.group(1))
    elif target_msg and target_msg.forward_from:
        tid = target_msg.forward_from.id

    feg_id_str = feg_id_match.group(0).upper() if feg_id_match else None
    uname_str = username_match.group(1) if username_match else (target_msg.forward_from.username if target_msg and target_msg.forward_from else None)
    raw_name = name_match.group(1).strip() if name_match else (target_msg.forward_from.full_name if target_msg and target_msg.forward_from else None)

    async with get_db_session() as session:
        user = None
        if tid:
            user = await MemberService.get_user_by_telegram_id(session, tid)
        if not user and feg_id_str:
            stmt = select(User).where(User.feg_member_id == feg_id_str)
            user = (await session.execute(stmt)).scalar_one_or_none()
        if not user and uname_str:
            stmt = select(User).where(User.telegram_username == uname_str)
            user = (await session.execute(stmt)).scalar_one_or_none()

        if not user and not tid:
            if target_msg and target_msg.from_user and target_msg.from_user.id != msg.from_user.id:
                tid = target_msg.from_user.id

        if not tid and not user:
            await safe_reply(
                msg,
                "⚠️ **COULD NOT EXTRACT MEMBER TELEGRAM ID**\n\n"
                "Please ensure the message contains `Telegram ID: 123456789`, `FEG-2026-XXXXXX`, or `@username`."
            )
            return

        if not user:
            user = await MemberService.get_or_start_registration(
                session=session,
                telegram_id=tid,
                full_name=raw_name or f"FEG Member {tid}",
                telegram_username=uname_str
            )
        else:
            if raw_name and raw_name not in ["Not set"]:
                user.full_name = raw_name
            if uname_str:
                user.telegram_username = uname_str

        user.registration_status = "COMMUNITY_ACCESS_GRANTED"

        # FPL Profile
        fpl_id = int(fpl_id_match.group(1)) if fpl_id_match else None
        manager_match = re.search(r"Manager:\s*([^\n\•\*\`]+)", text, re.IGNORECASE)
        team_match = re.search(r"Team:\s*([^\n\•\*\`]+)", text, re.IGNORECASE) or re.search(r"Team Name:\s*([^\n\•\*\`]+)", text, re.IGNORECASE)
        extracted_mgr = manager_match.group(1).strip() if manager_match else None
        extracted_team = team_match.group(1).strip() if team_match else None

        stmt_f = select(FPLProfile).where(FPLProfile.user_id == user.id)
        fpl_p = (await session.execute(stmt_f)).scalar_one_or_none()

        if fpl_id:
            mgr_name = extracted_mgr or user.full_name
            team_n = extracted_team or "FEG FC"

            if not fpl_p:
                fpl_p = FPLProfile(
                    user_id=user.id,
                    fpl_id=fpl_id,
                    manager_name=mgr_name,
                    team_name=team_n,
                    classic_status="VERIFIED",
                    h2h_status="VERIFIED"
                )
                session.add(fpl_p)
            else:
                fpl_p.fpl_id = fpl_id
                fpl_p.manager_name = mgr_name
                fpl_p.team_name = team_n
                fpl_p.classic_status = "VERIFIED"
                fpl_p.h2h_status = "VERIFIED"
        elif fpl_p and (extracted_mgr or extracted_team):
            if extracted_mgr:
                fpl_p.manager_name = extracted_mgr
            if extracted_team:
                fpl_p.team_name = extracted_team

        # Bank Account
        bname = bank_match.group(1).strip() if bank_match else "Palmpay"
        aname = acc_name_match.group(1).strip() if acc_name_match else user.full_name
        anum = acc_num_match.group(1).strip() if acc_num_match else "8066106785"

        stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        payout_p = (await session.execute(stmt_p)).scalar_one_or_none()
        enc_num = encrypt_string(anum)
        masked_num = mask_account_number(anum)

        if not payout_p:
            payout_p = PayoutAccount(
                user_id=user.id,
                bank_name=bname,
                account_name=aname,
                encrypted_account_number=enc_num,
                masked_account_number=masked_num
            )
            session.add(payout_p)
        else:
            payout_p.bank_name = bname
            payout_p.account_name = aname
            payout_p.encrypted_account_number = enc_num
            payout_p.masked_account_number = masked_num

        await session.commit()
        full_acc_num = anum
        if payout_p and payout_p.encrypted_account_number:
            try:
                full_acc_num = decrypt_string(payout_p.encrypted_account_number)
            except Exception:
                full_acc_num = anum

        card = (
            "✅ **MEMBER RECORD PARSED & RESTORED!**\n\n"
            "👤 **MEMBER DETAILS:**\n"
            f"• **Full Name:** {escape_markdown(user.full_name)}\n"
            f"• **FEG Member ID:** `{user.feg_member_id}`\n"
            f"• **Telegram:** @{escape_markdown(user.telegram_username or 'NoUsername')} (`{user.telegram_id}`)\n\n"
            "⚽️ **FPL DETAILS:**\n"
            f"• **FPL ID:** `{fpl_id or (fpl_p.fpl_id if fpl_p else 'Not set')}`\n"
            f"• **Manager:** {escape_markdown(fpl_p.manager_name if fpl_p else user.full_name)}\n"
            f"• **Team:** {escape_markdown(fpl_p.team_name if fpl_p else 'FEG FC')}\n\n"
            "🏦 **PAYOUT BANK DETAILS:**\n"
            f"• **Bank:** {escape_markdown(bname)}\n"
            f"• **Account Name:** {escape_markdown(aname)}\n"
            f"• **Account Number:** `{full_acc_num}`"
        )
        await safe_reply(msg, card)


@admin_required()
async def admin_pending_payments_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    target_message = update.callback_query.message if update.callback_query else update.message

    async with get_db_session() as session:
        stmt = select(Payment).where(Payment.payment_status == "PENDING").order_by(Payment.created_at.asc())
        res = await session.execute(stmt)
        pending_payments = res.scalars().all()

        if not pending_payments:
            await safe_reply(target_message, "✅ **NO PENDING PAYMENTS**\n\nAll member payment submissions have been reviewed and processed.")
            return

        await safe_reply(target_message, f"💳 **FOUND {len(pending_payments)} PENDING PAYMENT(S) TO REVIEW:**")

        for pay in pending_payments:
            try:
                stmt_u = select(User).where(User.id == pay.user_id)
                user = (await session.execute(stmt_u)).scalar_one_or_none()
                if not user:
                    continue

                stmt_fpl = select(FPLProfile).where(FPLProfile.user_id == user.id)
                fpl = (await session.execute(stmt_fpl)).scalar_one_or_none()

                stmt_payout = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
                payout = (await session.execute(stmt_payout)).scalar_one_or_none()

                fpl_id_str = str(fpl.fpl_id) if fpl else "N/A"
                manager_name = fpl.manager_name if fpl else "N/A"
                team_name = fpl.team_name if fpl else "N/A"

                payout_bank = payout.bank_name if payout else "N/A"
                payout_acc_name = payout.account_name if payout else "N/A"
                payout_acc_num = payout.masked_account_number if payout else "N/A"

                card_msg = (
                    "💳 **NEW PAYMENT SUBMISSION FOR REVIEW**\n\n"
                    "👤 **MEMBER DETAILS:**\n"
                    f"• **Full Name:** {user.full_name}\n"
                    f"• **FEG Member ID:** `{user.feg_member_id}`\n"
                    f"• **Telegram ID:** `{user.telegram_id}` (@{user.telegram_username or 'NoUsername'})\n"
                    f"• **Referral Code:** `{user.referral_code}`\n\n"
                    "⚽ **FPL DETAILS:**\n"
                    f"• **FPL ID:** `{fpl_id_str}`\n"
                    f"• **Manager:** {manager_name}\n"
                    f"• **Team:** {team_name}\n\n"
                    "🏦 **PAYOUT BANK DETAILS:**\n"
                    f"• **Bank:** {payout_bank}\n"
                    f"• **Account Name:** {payout_acc_name}\n"
                    f"• **Account Number:** `{payout_acc_num}`\n\n"
                    "💰 **PAYMENT DETAILS:**\n"
                    f"• **Amount:** ₦{pay.amount:,.0f}\n"
                    f"• **Method:** {pay.payment_method}\n"
                    f"• **Account Version:** v{pay.payment_account_version}\n"
                    f"• **Submitted:** {pay.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    "• **Status:** 🟡 PENDING ADMIN REVIEW\n\n"
                    "📷 **Proof Screenshot:** Attached below"
                )

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ APPROVE PAYMENT", callback_data=f"approve_pay_{pay.id}"),
                        InlineKeyboardButton("❌ REJECT PAYMENT", callback_data=f"reject_pay_{pay.id}")
                    ]
                ])

                if pay.proof_file_id:
                    try:
                        await target_message.reply_photo(
                            photo=pay.proof_file_id,
                            caption=card_msg,
                            reply_markup=keyboard,
                            parse_mode="Markdown"
                        )
                    except Exception:
                        await safe_reply(target_message, card_msg, reply_markup=keyboard)
                else:
                    await safe_reply(target_message, card_msg, reply_markup=keyboard)
            except Exception as pay_err:
                logger.error(f"Error rendering pending payment card for payment {pay.id}: {pay_err}")


@admin_required()
async def admin_referrals_tracker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.callback_query.message if update.callback_query else update.message

    async with get_db_session() as session:
        stmt = (
            select(User, func.count(Referral.id).label("ref_cnt"))
            .join(Referral, User.id == Referral.referrer_user_id)
            .group_by(User.id)
            .order_by(func.count(Referral.id).desc())
            .limit(10)
        )
        res = await session.execute(stmt)
        top_referrers = res.all()

        if not top_referrers:
            await safe_reply(target_msg, "👥 **FEG REFERRAL TRACKER**\n\nNo referral milestone activity recorded yet.")
            return

        lines = []
        for idx, (user, count) in enumerate(top_referrers, 1):
            milestone, amount = ReferralService.calculate_milestone_reward(count)
            lines.append(f"{idx}. **{user.full_name}** (`{user.feg_member_id}`) — Invites: `{count}` | Milestone: `{milestone}` (₦{amount:,})")

        msg = (
            "👥 **FEG REFERRAL TRACKER & LEADERBOARD**\n\n"
            + "\n".join(lines) +
            "\n\nℹ️ *Use `/search_member FEG_ID` to inspect individual payout bank details before approving milestone cash payouts.*"
        )
        await safe_reply(target_msg, msg)


@admin_required()
async def announce_gw_winner_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    gw_num = int(args[0]) if args and args[0].isdigit() else 4
    gw_num = max(gw_num, 4)

    gw, formation, players, total_pts = await FPLService.get_official_team_of_gw(gw_num)
    top_player_name = players[0]["name"] if players else "FPL Manager"

    announcement = (
        f"🏆 **FEG MANAGER OF THE WEEK — GAMEWEEK {gw_num}** 👑\n\n"
        f"🥇 **Gameweek Winner:** {top_player_name}\n"
        f"⚽ **Top Score:** `{total_pts} PTS` (Formation: {formation})\n"
        "💰 **Cash Reward:** ₦1,000\n\n"
        "🎉 Congratulations to our Gameweek Champion! FEG Admin has been notified for direct bank transfer."
    )

    if settings.FEG_COMMUNITY_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=settings.FEG_COMMUNITY_CHAT_ID,
                text=announcement,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not post GW winner to community chat: {e}")

    await safe_reply(
        update.message,
        f"✅ **GAMEWEEK {gw_num} WINNER ANNOUNCED!**\n\n"
        f"{announcement}\n\n"
        "💡 *Alert sent to Finance Admin to disburse ₦1,000 reward.*"
    )


@admin_required("SUPER_ADMIN")
async def admin_payment_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_msg = update.callback_query.message if update.callback_query else update.message
    async with get_db_session() as session:
        active_config = await get_latest_active_payment_account(session)
        ver = active_config.version if active_config else 1
        bank = active_config.bank_name if active_config else settings.FEG_PAYMENT_BANK
        name = active_config.account_name if active_config else settings.FEG_PAYMENT_ACCOUNT_NAME
        num = active_config.account_number if active_config else settings.FEG_PAYMENT_ACCOUNT_NUMBER

    msg = (
        "🏦 **FEG RECEIVING PAYMENT ACCOUNT CONFIGURATION**\n\n"
        f"**Active Version:** v{ver}\n"
        f"**Bank:** {bank}\n"
        f"**Account Name:** {name}\n"
        f"**Account Number:** `{num}`\n\n"
        "To update the receiving bank account, send command:\n"
        "`/set_pay_account BankName | AccountName | AccountNumber`"
    )
    await safe_reply(target_msg, msg)


@admin_required("SUPER_ADMIN")
async def admin_set_payment_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.replace("/set_pay_account", "").strip()
    parts = [p.strip() for p in text_input.split("|")]
    if len(parts) != 3:
        await safe_reply(
            update.message,
            "⚠️ Invalid format.\nUse: `/set_pay_account BankName | AccountName | AccountNumber`"
        )
        return

    bank_name, account_name, account_number = parts
    admin_user = update.effective_user

    async with get_db_session() as session:
        new_cfg = await create_payment_account_config(
            session=session,
            bank_name=bank_name,
            account_name=account_name,
            account_number=account_number
        )
        await add_audit_log(
            session=session,
            admin_id=admin_user.id,
            role="SUPER_ADMIN",
            action="UPDATED_PAYMENT_ACCOUNT_CONFIG",
            target=f"Version v{new_cfg.version}",
            details=f"Updated receiving bank account to {bank_name} / {account_name} / {account_number}"
        )

    msg = (
        "✅ **FEG RECEIVING ACCOUNT UPDATED**\n\n"
        f"**New Version:** v{new_cfg.version}\n"
        f"**Bank:** {bank_name}\n"
        f"**Account Name:** {account_name}\n"
        f"**Account Number:** `{account_number}`\n\n"
        "All future registration payments will now use this versioned configuration."
    )
    await safe_reply(update.message, msg)


@admin_required()
async def admin_generic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    target_msg = query.message

    if data in ["admin_payments", "admin_payments_pending"]:
        return await admin_pending_payments_handler(update, context)
    elif data == "admin_members":
        return await admin_members_list_handler(update, context)
    elif data == "admin_referrals":
        return await admin_referrals_tracker_handler(update, context)
    elif data == "admin_audit_logs":
        return await admin_audit_logs_handler(update, context)
    elif data == "admin_refresh":
        return await admin_dashboard_handler(update, context)
    elif data == "admin_pay_account":
        return await admin_payment_account_handler(update, context)

    # Super Admin Engine Modules
    if data == "admin_fpl_engine":
        curr_gw = await FPLService.get_current_or_next_gameweek()
        msg = (
            "⚽ **FEG FPL ENGINE STATUS & CONFIG**\n\n"
            f"• **FPL API Status:** ONLINE\n"
            f"• **Active Gameweek:** {curr_gw.get('name', 'Gameweek 4')}\n"
            f"• **Deadline:** {curr_gw.get('deadline_time', 'TBD')}\n"
            f"• **Classic League ID:** `{settings.FPL_CLASSIC_LEAGUE_ID}`\n"
            f"• **H2H League ID:** `{settings.FPL_H2H_LEAGUE_ID}`\n"
            "• **Data Sync Interval:** Real-time on command trigger"
        )
        await safe_reply(target_msg, msg)

    elif data == "admin_live_engine":
        msg = (
            "🔴 **FEG LIVE MATCH ENGINE**\n\n"
            "• **Live Feed Status:** ACTIVE\n"
            "• **Scoring Engine:** Official FPL Event Feed\n"
            "• **Manager of the Week:** Automated GW Winner Detection\n"
            "• **Gameweek Kickoff:** Official competition scoring begins Gameweek 4!"
        )
        await safe_reply(target_msg, msg)

    elif data == "admin_stats_engine":
        msg = (
            "📈 **FEG STATISTICS ENGINE**\n\n"
            "• **Player Analytics:** Form, total points & ICT index\n"
            "• **Price Watch:** Real-time transfer in/out volume tracking\n"
            "• **Differentials:** Low ownership picks (< 10% ownership)\n"
            "• **Commands:** `/captain`, `/differentials`, `/pricewatch`"
        )
        await safe_reply(target_msg, msg)

    elif data == "admin_content_engine":
        msg = (
            "📰 **FEG CONTENT & MEDIA ENGINE**\n\n"
            "• **Graphics Engine:** PIL High-Resolution Team of the GW Generator\n"
            "• **Pinned Templates:** `/announcement_template`\n"
            "• **Media Commands:** `/preview`, `/teamofgw`, `/captain`\n"
            "• **Hall of Fame:** `/halloffame_classic`, `/halloffame_h2h`, `/halloffame_cup`"
        )
        await safe_reply(target_msg, msg)

    elif data == "admin_sys_health":
        db_status = "ONLINE"
        try:
            async with get_db_session() as session:
                await session.execute(text("SELECT 1"))
        except Exception as e:
            db_status = f"OFFLINE ({e})"

        msg = (
            "🟢 **FEG SYSTEM HEALTH & DIAGNOSTICS**\n\n"
            "🤖 **Bot Engine:** ONLINE\n"
            f"🗄️ **SQLite Database:** {db_status}\n"
            "🔐 **Admin Auth & Dynamic Promotion:** ACTIVE\n"
            "🔒 **AES-256 Crypto Engine:** ACTIVE\n"
            "🌐 **FPL API Connection:** ONLINE"
        )
        await safe_reply(target_msg, msg)

    elif data in ["admin_settings", "admin_competitions"]:
        msg = (
            "⚙️ **FEG SYSTEM SETTINGS & CONFIGURATION**\n\n"
            f"• **Registration Fee:** ₦{settings.FEG_REGISTRATION_FEE:,}\n"
            f"• **Receiving Bank:** {settings.FEG_PAYMENT_BANK}\n"
            f"• **Account Name:** {settings.FEG_PAYMENT_ACCOUNT_NAME}\n"
            f"• **Account Number:** `{settings.FEG_PAYMENT_ACCOUNT_NUMBER}`\n"
            f"• **Classic Code:** `{settings.FPL_CLASSIC_INVITE_CODE}`\n"
            f"• **H2H Code:** `{settings.FPL_H2H_INVITE_CODE}`\n\n"
            "To update the receiving bank account, use `/set_pay_account Bank | Name | AccountNumber`."
        )
        await safe_reply(target_msg, msg)
