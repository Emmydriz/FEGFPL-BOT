from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_db_session
from database.models import User, FPLProfile, PayoutAccount, Referral, Reward
from services.member_service import MemberService
from services.fpl_service import FPLService
from services.referral_service import ReferralService
from services.hall_of_fame_service import HallOfFameService
from services.auth_service import approved_member_required
from config.settings import settings
from config.logging_config import logger
from sqlalchemy import select, func


from bot.utils import escape_markdown


@approved_member_required()
async def member_profile_dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg = update.effective_user
    chat_id = update.effective_chat.id

    async with get_db_session() as session:
        user = await MemberService.get_user_by_telegram_id(session, user_tg.id)
        if not user:
            msg = (
                "⚠️ **NOT REGISTERED**\n\n"
                "You have not completed FEG FPL registration yet.\n"
                "Type `/start` or `/register` to begin!"
            )
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

        stmt_fpl = select(FPLProfile).where(FPLProfile.user_id == user.id)
        fpl = (await session.execute(stmt_fpl)).scalar_one_or_none()

        stmt_payout = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        payout = (await session.execute(stmt_payout)).scalar_one_or_none()

        fpl_id = str(fpl.fpl_id) if fpl else "Not set"
        manager_name = fpl.manager_name if fpl else "Not set"
        team_name = fpl.team_name if fpl else "Not set"

        bank_name = payout.bank_name if payout else "Not set"
        account_name = payout.account_name if payout else "Not set"
        account_number = payout.masked_account_number if payout else "Not set"

        # Count referrals
        stmt_ref = select(func.count(Referral.id)).where(Referral.referrer_user_id == user.id)
        ref_count = (await session.execute(stmt_ref)).scalar() or 0

        # Total rewards
        stmt_rew = select(func.sum(Reward.amount)).where(Reward.user_id == user.id, Reward.status == "PAID")
        total_rewards = (await session.execute(stmt_rew)).scalar() or 0.0

        bot_name = "FEGFPL_Bot"
        if context.bot and context.bot.username:
            bot_name = context.bot.username

        ref_link = f"https://t.me/{bot_name}?start=ref_{user.referral_code}"

        # Escape dynamic string fields to prevent Telegram Markdown parsing errors
        safe_full_name = escape_markdown(user.full_name)
        safe_tg_username = escape_markdown(user.telegram_username) if user.telegram_username else "NoUsername"
        safe_manager_name = escape_markdown(manager_name)
        safe_team_name = escape_markdown(team_name)
        safe_bank_name = escape_markdown(bank_name)
        safe_account_name = escape_markdown(account_name)
        classic_badge = "✅ VERIFIED IN LEAGUE" if (fpl and fpl.classic_status == "VERIFIED") else "🟡 PENDING (Click Verify)"
        h2h_badge = "✅ VERIFIED IN LEAGUE" if (fpl and fpl.h2h_status == "VERIFIED") else "🟡 PENDING (Click Verify)"

        msg = (
            "👤 **FEG MEMBER PROFILE & DASHBOARD**\n\n"
            f"• **Full Name:** {safe_full_name}\n"
            f"• **FEG Member ID:** `{user.feg_member_id}`\n"
            f"• **Registration Status:** `{user.registration_status}`\n"
            f"• **Telegram ID:** `{user.telegram_id}` (@{safe_tg_username})\n\n"
            "⚽ **FPL PROFILE & LEAGUE VERIFICATION:**\n"
            f"• **FPL ID:** `{fpl_id}`\n"
            f"• **Manager:** {safe_manager_name}\n"
            f"• **Team Name:** {safe_team_name}\n"
            f"• **Classic League Status:** {classic_badge}\n"
            f"• **H2H League Status:** {h2h_badge}\n\n"
            "🏦 **PAYOUT BANK ACCOUNT:**\n"
            f"• **Bank:** {safe_bank_name}\n"
            f"• **Account Name:** {safe_account_name}\n"
            f"• **Account Number:** `{account_number}`\n\n"
            "👥 **REFERRALS & REWARDS:**\n"
            f"• **Referral Code:** `{user.referral_code}`\n"
            f"• **Total Invites:** `{ref_count}` members\n"
            f"• **Rewards Earned:** ₦{total_rewards:,.0f}\n"
            f"• **Your Personal Referral Link:**\n`{ref_link}`"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 CLASSIC LEAGUE", callback_data="view_classic"), InlineKeyboardButton("⚔️ H2H LEAGUE", callback_data="view_h2h")],
            [InlineKeyboardButton("🥊 FEG CUP", callback_data="view_cup"), InlineKeyboardButton("🔄 VERIFY MEMBERSHIP", callback_data=f"verify_{user.id}")]
        ])

        try:
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
        except Exception as err:
            logger.error(f"Markdown error in member_profile_dashboard_handler: {err}")
            plain_msg = msg.replace("**", "").replace("`", "").replace("\\", "")
            target_msg = update.callback_query.message if update.callback_query else update.message
            await target_msg.reply_text(plain_msg, reply_markup=keyboard)


@approved_member_required()
async def classic_dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🏆 **FEG CLASSIC LEAGUE**\n\n"
        f"• **League Name:** FEG Classic League 2026\n"
        f"• **Official League ID:** `{settings.FPL_CLASSIC_LEAGUE_ID}`\n"
        f"• **Invite Code:** `{settings.FPL_CLASSIC_INVITE_CODE}`\n"
        f"• **Direct Join Link:** [Click to Join Classic League]({settings.FPL_CLASSIC_INVITE_LINK})\n\n"
        "💡 *Join the official Classic League on Fantasy Premier League to compete for Gameweek & Season cash prizes!*"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 VIEW STANDINGS", callback_data="view_classic_standings")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)


@approved_member_required()
async def h2h_dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "⚔️ **FEG HEAD-TO-HEAD (H2H) LEAGUE**\n\n"
        f"• **League Name:** FEG H2H League 2026\n"
        f"• **Official League ID:** `{settings.FPL_H2H_LEAGUE_ID}`\n"
        f"• **Invite Code:** `{settings.FPL_H2H_INVITE_CODE}`\n"
        f"• **Direct Join Link:** [Click to Join H2H League]({settings.FPL_H2H_INVITE_LINK})\n\n"
        "💡 *Go head-to-head weekly against fellow FEG community managers!*"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 VIEW H2H STANDINGS", callback_data="view_h2h_standings")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)


@approved_member_required()
async def cup_dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_info = await HallOfFameService.poll_fpl_cup_status()

    status_tag = status_info.get("status", "UNOPENED")
    message = status_info.get("message", "")
    member_cnt = status_info.get("member_count", 0)

    msg = (
        "🥊 **FEG KNOCKOUT CUP COMPETITION & LIVE STATUS** ⚽\n\n"
        f"• **Current Private League Members:** `{member_cnt}`\n"
        f"• **FPL API Cup Status:** `{status_tag}`\n"
        "• **Qualification & Start Gameweek:** Automatically determined by FPL API when our Classic Private League reaches FPL's required member threshold (8, 16, 32, 64+ managers).\n"
        "• **Tournament Format:** Single-Elimination Knockout Bracket.\n\n"
        "👑 **CUP WINNER TITLE & PRESTIGE:**\n"
        "• **Prize Structure:** The FEG Knockout Cup is a pure prestige competition (no cash prize).\n"
        "• **Championship Title:** The Cup Winner is automatically crowned **'The Untouchable'**, enshrined in the Hall of Fame (`/halloffame_cup`), and carries the title into the following season as defending champion!\n\n"
        f"📋 **LIVE FPL CUP QUALIFICATION DETAILS:**\n"
        f"{message}\n\n"
        "💡 *Join our Classic League via `/classic` before FPL opens qualification to participate in the Knockout Cup!*"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 VIEW REIGNING TITLEHOLDER", callback_data="view_champion_cup")],
        [InlineKeyboardButton("🏛️ VIEW CUP HALL OF FAME", callback_data="view_halloffame_cup")]
    ])

    target_msg = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()

    try:
        await target_msg.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    except Exception:
        plain_msg = msg.replace("**", "").replace("`", "")
        await target_msg.reply_text(plain_msg, reply_markup=keyboard)


async def verify_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.data.replace("verify_", "")

    async with get_db_session() as session:
        stmt = select(User).where(User.id == int(user_id))
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            await query.message.reply_text("⚠️ User record not found.", parse_mode="Markdown")
            return

        stmt_fpl = select(FPLProfile).where(FPLProfile.user_id == user.id)
        fpl = (await session.execute(stmt_fpl)).scalar_one_or_none()

        if not fpl:
            await query.message.reply_text("⚠️ FPL Profile not found.", parse_mode="Markdown")
            return

        fpl_id = fpl.fpl_id
        is_classic = await FPLService.check_league_membership(settings.FPL_CLASSIC_LEAGUE_ID, fpl_id, "classic")
        is_h2h = await FPLService.check_league_membership(settings.FPL_H2H_LEAGUE_ID, fpl_id, "h2h")

        msg = (
            "🔄 **LEAGUE MEMBERSHIP VERIFICATION**\n\n"
            f"**Member:** {user.full_name} (`{user.feg_member_id}`)\n"
            f"**FPL ID:** `{fpl_id}`\n\n"
            f"• **Classic League Status:** {'✅ VERIFIED IN LEAGUE' if is_classic else '❌ NOT FOUND IN CLASSIC LEAGUE'}\n"
            f"• **H2H League Status:** {'✅ VERIFIED IN LEAGUE' if is_h2h else '❌ NOT FOUND IN H2H LEAGUE'}\n\n"
            "If not joined, use the join links in `/classic` and `/h2h`."
        )
        await query.message.reply_text(msg, parse_mode="Markdown")


@approved_member_required()
async def standings_classic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    league_name, standings = await FPLService.get_league_standings(settings.FPL_CLASSIC_LEAGUE_ID, "classic")

    if not standings:
        msg = f"🏆 **{league_name} STANDINGS**\n\nLeague standings will update live on official FPL Gameweek kickoff!"
    else:
        lines = []
        for idx, s in enumerate(standings[:10], 1):
            lines.append(f"{idx}. **{s.get('entry_name')}** ({s.get('player_name')}) — `{s.get('total')} PTS`")
        msg = f"🏆 **{league_name} TOP 10 STANDINGS**\n\n" + "\n".join(lines)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")


@approved_member_required()
async def standings_h2h_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    league_name, standings = await FPLService.get_league_standings(settings.FPL_H2H_LEAGUE_ID, "h2h")

    if not standings:
        msg = f"⚔️ **{league_name} STANDINGS**\n\nH2H matchups will update live on official FPL Gameweek kickoff!"
    else:
        lines = []
        for idx, s in enumerate(standings[:10], 1):
            lines.append(f"{idx}. **{s.get('entry_name')}** ({s.get('player_name')}) — `{s.get('total')} PTS` (W:{s.get('matches_won',0)} D:{s.get('matches_drawn',0)} L:{s.get('matches_lost',0)})")
        msg = f"⚔️ **{league_name} TOP 10 STANDINGS**\n\n" + "\n".join(lines)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")


@approved_member_required()
async def motw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    gw_num = int(args[0]) if args and args[0].isdigit() else 4
    gw_num = max(gw_num, 4)

    gw, formation, players, total_pts = await FPLService.get_official_team_of_gw(gw_num)

    msg = (
        f"👑 **FEG MANAGER OF THE WEEK — GAMEWEEK {gw}**\n\n"
        f"• **Gameweek Kickoff:** GW4\n"
        f"• **Top Formation:** {formation}\n"
        f"• **Top Gameweek Score:** `{total_pts} PTS`\n"
        "• **Reward Amount:** ₦1,000 Cash Prize\n\n"
        "🏆 *Official Manager of the Week scoring starts in Gameweek 4! Winner is awarded a ₦1,000 cash prize after every Gameweek.*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


@approved_member_required()
async def set_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "✏️ **UPDATE YOUR FULL NAME**\n\n"
            "Please provide your updated full name.\n"
            "Usage: `/setname Firstname Lastname`",
            parse_mode="Markdown"
        )
        return

    new_name = " ".join(args).strip()
    user_tg = update.effective_user

    async with get_db_session() as session:
        user = await MemberService.get_user_by_telegram_id(session, user_tg.id)
        if user:
            user.full_name = new_name
            await session.commit()
            await update.message.reply_text(
                f"✅ **FULL NAME UPDATED!**\n\nYour profile full name has been updated to: **{escape_markdown(new_name)}**",
                parse_mode="Markdown"
            )


@approved_member_required()
async def set_fpl_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "⚽ **UPDATE YOUR FPL ID**\n\n"
            "Please provide your numerical FPL ID.\n"
            "Usage: `/setfpl 123456`",
            parse_mode="Markdown"
        )
        return

    fpl_id = int(args[0])
    user_tg = update.effective_user

    async with get_db_session() as session:
        user = await MemberService.get_user_by_telegram_id(session, user_tg.id)
        if user:
            manager_name, team_name = await FPLService.get_user_fpl_details(fpl_id)
            stmt_fpl = select(FPLProfile).where(FPLProfile.user_id == user.id)
            fpl = (await session.execute(stmt_fpl)).scalar_one_or_none()

            is_classic = await FPLService.check_league_membership(settings.FPL_CLASSIC_LEAGUE_ID, fpl_id, "classic")
            is_h2h = await FPLService.check_league_membership(settings.FPL_H2H_LEAGUE_ID, fpl_id, "h2h")

            if not fpl:
                fpl = FPLProfile(
                    user_id=user.id,
                    fpl_id=fpl_id,
                    manager_name=manager_name or "Manager",
                    team_name=team_name or "Team",
                    classic_status="VERIFIED" if is_classic else "PENDING",
                    h2h_status="VERIFIED" if is_h2h else "PENDING"
                )
                session.add(fpl)
            else:
                fpl.fpl_id = fpl_id
                if manager_name:
                    fpl.manager_name = manager_name
                if team_name:
                    fpl.team_name = team_name
                fpl.classic_status = "VERIFIED" if is_classic else "PENDING"
                fpl.h2h_status = "VERIFIED" if is_h2h else "PENDING"

            await session.commit()
            msg = (
                "✅ **FPL PROFILE UPDATED & VERIFIED!**\n\n"
                f"• **FPL ID:** `{fpl_id}`\n"
                f"• **Manager:** {escape_markdown(fpl.manager_name)}\n"
                f"• **Team Name:** {escape_markdown(fpl.team_name)}\n"
                f"• **Classic Status:** {'✅ VERIFIED IN LEAGUE' if is_classic else '🟡 PENDING'}\n"
                f"• **H2H Status:** {'✅ VERIFIED IN LEAGUE' if is_h2h else '🟡 PENDING'}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")


@approved_member_required()
async def set_bank_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("/setbank", "").strip()
    parts = [p.strip() for p in text.split("|") if p.strip()]

    if len(parts) != 3:
        await update.message.reply_text(
            "🏦 **UPDATE PAYOUT BANK ACCOUNT**\n\n"
            "Please provide your Bank Name, Account Name, and Account Number separated by `|`.\n\n"
            "Usage: `/setbank Palmpay | Odeyemi Omogbolahan | 8066106785`",
            parse_mode="Markdown"
        )
        return

    bank_name, account_name, account_number = parts
    user_tg = update.effective_user

    async with get_db_session() as session:
        user = await MemberService.get_user_by_telegram_id(session, user_tg.id)
        if user:
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
            msg = (
                "✅ **PAYOUT BANK ACCOUNT UPDATED!**\n\n"
                f"• **Bank:** {escape_markdown(bank_name)}\n"
                f"• **Account Name:** {escape_markdown(account_name)}\n"
                f"• **Account Number:** `{masked_num}`"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
