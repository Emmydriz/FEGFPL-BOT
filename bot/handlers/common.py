from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.settings import settings
from database.db import get_db_session
from sqlalchemy import text
from bot.keyboards import get_member_start_keyboard
from config.logging_config import logger


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Capture referral code from start payload (e.g. /start ref_FEG-REF-000001 or /start FEG-REF-000001)
    if context.args:
        raw_arg = context.args[0].strip()
        ref_code = None
        if raw_arg.startswith("ref_"):
            ref_code = raw_arg.replace("ref_", "")
        elif raw_arg.startswith("FEG-REF-"):
            ref_code = raw_arg
        else:
            ref_code = raw_arg

        if ref_code:
            context.user_data["referrer_code"] = ref_code
            logger.info(f"Captured referral code '{ref_code}' for Telegram User ID {user.id}")

            try:
                from services.member_service import MemberService
                from services.referral_service import ReferralService
                async with get_db_session() as session:
                    db_user = await MemberService.get_user_by_telegram_id(session, user.id)
                    if db_user and not db_user.referred_by_id:
                        await ReferralService.record_referral(
                            session=session,
                            referrer_code=ref_code,
                            new_user=db_user
                        )
                        await session.commit()
            except Exception as e:
                logger.warning(f"Could not record referral code during start_handler: {e}")

    # Check user approval status
    is_approved = False
    async with get_db_session() as session:
        from services.auth_service import AuthService
        from services.member_service import MemberService
        if AuthService.is_authorized_admin(user.id):
            is_approved = True
        else:
            db_user = await MemberService.get_user_by_telegram_id(session, user.id)
            if db_user and db_user.registration_status in ["APPROVED", "COMMUNITY_ACCESS_GRANTED"]:
                is_approved = True
            elif settings.FEG_COMMUNITY_CHAT_ID:
                try:
                    chat_member = await context.bot.get_chat_member(
                        chat_id=settings.FEG_COMMUNITY_CHAT_ID,
                        user_id=user.id
                    )
                    if chat_member and chat_member.status in ["member", "administrator", "creator"]:
                        if not db_user:
                            db_user = await MemberService.get_or_start_registration(
                                session=session,
                                telegram_id=user.id,
                                full_name=user.full_name,
                                telegram_username=user.username
                            )
                        db_user.registration_status = "COMMUNITY_ACCESS_GRANTED"
                        await session.commit()
                        is_approved = True
                        logger.info(f"Auto-restored member account for Telegram User ID {user.id} ({user.full_name}) found in community group.")
                except Exception as ex:
                    logger.warning(f"Could not verify group chat membership for Telegram User {user.id}: {ex}")

    if not is_approved:
        # Unapproved / New Registering Member View (Commands Directory NOT Revealed)
        msg = (
            "⚽ **WELCOME TO FEG FPL** ⚽\n\n"
            "Welcome to the official **FEG FPL** community and competition platform!\n\n"
            "To join our private community and participate in official weekly & season competitions, "
            "you must complete registration and verification.\n\n"
            f"💳 **Registration Fee:** ₦{settings.FEG_REGISTRATION_FEE:,}\n"
            f"📱 **Detected Telegram ID:** `{user.id}` (Auto-recorded)\n\n"
            "ℹ️ **Registration Reassurance:** Do not worry if you make a mistake! "
            "You will be shown a full summary review screen to verify and edit all your information before payment.\n\n"
            "Click the button below or type `/register` to begin registration."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 START REGISTRATION", callback_data="start_registration")],
            [InlineKeyboardButton("💳 VIEW RECEIVING BANK ACCOUNT", callback_data="show_pay_info")]
        ])
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
        return

    # Approved Member View (Commands Directory Revealed)
    msg = (
        "⚽ **WELCOME BACK TO FEG FPL** 🏆\n\n"
        f"Hi **{user.full_name}**! Your FEG Community access is active.\n\n"
        "📌 **YOUR MEMBER COMMANDS DIRECTORY:**\n\n"
        "👤 **PROFILE & DASHBOARD:**\n"
        "• `/profile` or `/dashboard` — View your FEG Member Profile, FPL details & bank account\n"
        "• `/info` — Inspect your registration & community status\n"
        "• `/referral` — Get your personal referral link & rewards\n\n"
        "🏆 **LEAGUES & STANDINGS:**\n"
        "• `/classic` — Join FEG Classic League (Code: `672262`)\n"
        "• `/h2h` — Join FEG H2H League (Code: `672209`)\n"
        "• `/cup` — FEG Cup status & eligibility\n"
        "• `/cupstatus` — Check live FPL Cup qualification threshold\n"
        "• `/motw` — View Manager of the Week info & top scores (starts GW4)\n"
        "• `/standings_classic` — Live top 10 Classic League standings\n"
        "• `/standings_h2h` — Live top 10 H2H League standings\n\n"
        "🏛️ **HALL OF FAME & CHAMPIONS:**\n"
        "• `/halloffame_classic` — View Classic League Hall of Fame\n"
        "• `/halloffame_h2h` — View H2H League Hall of Fame\n"
        "• `/halloffame_cup` — View Cup Hall of Fame ('The Untouchable')\n"
        "• `/champion_classic` — Reigning Classic Champion\n"
        "• `/champion_h2h` — Reigning H2H Champion\n"
        "• `/champion_cup` — Reigning 'The Untouchable' Titleholder\n\n"
        "⚽ **FPL MEDIA & STATS ENGINE:**\n"
        "• `/captain` — Weekly Captain recommendations\n"
        "• `/differentials` — Differential player picks under 10%\n"
        "• `/pricewatch` — Player price risers & fallers watch\n"
        "• `/preview` — Gameweek preview & deadline\n"
        "• `/teamofgw` — Team of the Gameweek graphic\n"
        "• `/help` — Full command guide & support"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 OPEN MEMBER DASHBOARD", callback_data="open_dashboard")]
    ])
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = False
    is_approved = False

    async with get_db_session() as session:
        from services.auth_service import AuthService
        from services.member_service import MemberService

        is_admin = AuthService.is_authorized_admin(user.id)
        if is_admin:
            is_approved = True
        else:
            db_user = await MemberService.get_user_by_telegram_id(session, user.id)
            if db_user and db_user.registration_status in ["APPROVED", "COMMUNITY_ACCESS_GRANTED"]:
                is_approved = True

    if not is_approved:
        msg = (
            "❓ **FEG FPL REGISTRATION & HELP GUIDE**\n\n"
            "Welcome! You are currently unregistered or pending payment verification.\n\n"
            "📌 **AVAILABLE REGISTRATION COMMANDS:**\n"
            "• `/start` — Welcome screen & begin registration\n"
            "• `/register` — Interactively fill registration details\n"
            "• `/pay` or `/payment` — View official receiving bank account details\n"
            "• `/help` — Display this registration help guide\n\n"
            "🔒 *All member competition features (Leagues, Dashboard, Hall of Fame, FPL Media) will unlock automatically once your registration payment is verified by admin!*"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    admin_section = ""
    if is_admin:
        admin_section = (
            "\n⚡ **ADMINISTRATION COMMANDS (AUTHORIZED ADMINS ONLY):**\n"
            "• `/updateaccount` — Conversational state machine or one-shot command (`/updateaccount FEG-2026-000001 8066106785 Opay`) to update member bank details with unmasked admin view\n"
            "• `/admin` — Open interactive Admin Dashboard panel\n"
            "• `/pending` or `/payments` — Review pending payment receipt uploads\n"
            "• `/members` — Browse community members directory\n"
            "• `/search_member` or `/member` — Search member & inspect full unmasked profile\n"
            "• `/admin_update_member` — Direct member field update\n"
            "• `/start_new_season` — Initialize new season & calculate deadlines\n"
            "• `/purge_unrenewed` — Preview & soft-delete unrenewed members\n"
            "• `/record_hall_of_fame` — Record permanent season winner\n"
            "• `/trigger_renewal_reminders` — Trigger 3-week pre-purge DM reminders\n"
            "• `/export_members` — Download complete member database as CSV\n"
            "• `/admin_referrals` — Referral leaderboard & earnings tracker\n"
            "• `/audit_logs` — View system audit log history\n"
            "• `/announcement_template` — View master pinned community announcement\n"
        )

    # Approved Member Help Directory
    msg = (
        "❓ **FEG FPL COMMANDS & DETAILED USER GUIDE** ⚽\n\n"
        "Welcome to the official FEG FPL Commands Directory! Below is the complete list of available commands and their functions:\n\n"
        "👤 **MEMBER PROFILE & ACCOUNT MANAGEMENT:**\n"
        "• `/start` — Welcome screen & auto-login verification\n"
        "• `/profile` or `/dashboard` — View your FEG Member Profile, FPL details, membership status & payout account\n"
        "• `/setbank` — Update your personal payout bank details (`/setbank Bank Name | Account Name | Account Number`)\n"
        "• `/renew` — Submit annual membership renewal payment proof\n"
        "• `/pay` or `/payment` — View official FEG receiving bank account details\n\n"
        "🏆 **LEAGUES, COMPETITIONS & STANDINGS:**\n"
        "• `/classic` — Get FEG Classic League code (`672262`) & join link\n"
        "• `/h2h` — Get FEG Head-to-Head League code (`672209`) & join link\n"
        "• `/cup` — Check FEG Knockout Cup status & eligibility\n"
        "• `/cupstatus` — Poll live FPL Cup qualification threshold & status\n"
        "• `/motw` — View Manager of the Week info & top scores (starts GW4)\n"
        "• `/standings_classic` — View live top 10 Classic League standings\n"
        "• `/standings_h2h` — View live top 10 Head-to-Head League standings\n\n"
        "🏛️ **HALL OF FAME & REIGNING CHAMPIONS:**\n"
        "• `/halloffame_classic` — Classic League Hall of Fame history & phase breakdown\n"
        "• `/halloffame_h2h` — Head-to-Head Hall of Fame history & phase breakdown\n"
        "• `/halloffame_cup` — Knockout Cup Hall of Fame & 'The Untouchable' titleholders\n"
        "• `/champion_classic` — View reigning Classic League Champion\n"
        "• `/champion_h2h` — View reigning Head-to-Head Champion\n"
        "• `/champion_cup` — View reigning 'The Untouchable' Cup Titleholder\n\n"
        "👥 **REFERRALS & REWARDS PROGRAM:**\n"
        "• `/referral` — Get your personal referral link (`https://t.me/FEGFPL_Bot?start=FEG-REF-XXXXXX`) & track milestone earnings\n\n"
        "⚽ **FPL MEDIA & STATS ENGINE:**\n"
        "• `/captain` — Weekly Captain recommendations based on FPL fixture metrics\n"
        "• `/differentials` — Differential player picks under 10% ownership\n"
        "• `/pricewatch` — Player price risers & fallers watch\n"
        "• `/preview` — Gameweek preview & official FPL deadline reminders\n"
        "• `/teamofgw` — View Team of the Gameweek graphic\n\n"
        "⚙️ **SYSTEM DIAGNOSTICS:**\n"
        "• `/help` — Display this complete command guide\n"
        "• `/health` — System status & database health report\n"
        "• `/id` — Display your Telegram User & Chat ID\n"
        f"{admin_section}\n"
        "💡 *You can type any command in DM or use the interactive buttons on your Member Dashboard.*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def announcement_template_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📢 **FEG FPL 2026 — MASTER SYSTEM UPGRADE & COMMUNITY ANNOUNCEMENT** 📌\n\n"
        "Welcome to **FEG FPL**, the premier paid Telegram Fantasy Premier League community and competition platform!\n\n"
        "🎉 **WHAT'S NEW & INTRODUCED IN OUR BOT SYSTEM:**\n\n"
        "⚡ **1. ENHANCED ADMIN BANK MANAGEMENT (`/updateaccount`):**\n"
        "• Admins can now instantly update and verify member bank account details with full unmasked account visibility on the Admin Dashboard for seamless, error-free prize disbursements.\n"
        "• All bank details remain encrypted with AES-256 at rest for maximum security.\n\n"
        "📅 **2. DYNAMIC FPL SEASON PURGE ENGINE ('Built for Life'):**\n"
        "• Annual membership renewals and purge dates are now dynamically calculated directly from the official Premier League FPL API.\n"
        "• The purge cutoff is set to **exactly 2 weeks (14 days) before Gameweek 1** every year, ensuring smooth automated transitions for every new season!\n\n"
        "🛡️ **3. ZERO DATA LOSS GUARANTEE:**\n"
        "• All member profiles, referral links, FPL manager details, and bank records are automatically synchronized in real-time between our database and persistent JSON backup snapshots (`members_backup.json`). Your data is 100% safe across any system update or restart!\n\n"
        "👥 **4. REFERRAL MILESTONE CASH REWARDS:**\n"
        "• Share your unique referral link (`/referral`) to earn cash rewards:\n"
        "  - 3 Referrals ➡️ ₦2,000\n"
        "  - 5 Referrals ➡️ ₦4,000\n"
        "  - 7 Referrals ➡️ ₦6,000\n"
        "  - 10 Referrals ➡️ ₦10,000\n\n"
        "🏆 **FEG COMPETITIONS & PRIZE STRUCTURES:**\n"
        "• 👑 **Manager of the Week (MOTW):** Cash prize awarded after EVERY Gameweek (starting GW4) to the top scoring manager in our Classic League!\n"
        "• 🏆 **Classic League Championship:** End-of-season cash prize pool for overall top rankers!\n"
        "• ⚔️ **Head-to-Head (H2H) League:** Weekly match battles with cash prizes for H2H season leaders!\n"
        "• 🥊 **FEG Knockout Cup ('The Untouchable'):** Pure prestige tournament! The winner is crowned **'The Untouchable'**, enshrined in the Hall of Fame, and carries the title into the following season!\n\n"
        "📌 **MEMBER QUICK COMMANDS:**\n"
        "• `/profile` or `/dashboard` — View your member profile, status & payout bank details.\n"
        "• `/setbank` — Update your personal payout bank details.\n"
        "• `/classic` — Get Classic League code & join link.\n"
        "• `/h2h` — Get H2H League code & join link.\n"
        "• `/cupstatus` — Poll live FPL Cup status.\n"
        "• `/referral` — Get your personal referral link & rewards.\n"
        "• `/help` — View the full interactive command guide.\n\n"
        "💡 *Make sure you join both the Classic and H2H leagues via the bot before Gameweek 4 to remain eligible for all Gameweek and Season cash rewards!*"
    )
    try:
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Markdown error in announcement_template_handler: {e}")
        plain_msg = msg.replace("**", "").replace("`", "")
        await update.message.reply_text(plain_msg)


async def health_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_status = "ONLINE"
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"OFFLINE ({e})"

    msg = (
        "🟢 **FEG FPL SYSTEM HEALTH**\n\n"
        f"🤖 **Bot Engine:** ONLINE\n"
        f"🗄️ **Database:** {db_status}\n"
        f"🔐 **Admin Auth System:** ACTIVE\n"
        f"💳 **Payment Method:** {settings.FEG_PAYMENT_METHOD}\n"
        f"🏦 **Receiving Bank:** {settings.FEG_PAYMENT_BANK}\n"
        f"👤 **Account Name:** {settings.FEG_PAYMENT_ACCOUNT_NAME}\n"
        f"🔢 **Account Number:** `{settings.FEG_PAYMENT_ACCOUNT_NUMBER}`\n\n"
        "FEG FPL Bot Core is running and healthy."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = (
        "🆔 **TELEGRAM CHAT & USER IDENTIFIERS**\n\n"
        f"• **Chat Title/Type:** {chat.title or chat.type}\n"
        f"• **Chat ID:** `{chat.id}`\n"
        f"• **Your User ID:** `{user.id}` (@{user.username or 'NoUsername'})\n\n"
        "💡 *If configuring channel or group IDs in .env, copy the Chat ID above.*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
