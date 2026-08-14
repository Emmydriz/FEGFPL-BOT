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

    # Approved Member Help
    msg = (
        "❓ **FEG FPL COMMANDS & HELP DIRECTORY**\n\n"
        "Here are all the available commands you can use in private DM:\n\n"
        "👤 **MEMBER COMMANDS:**\n"
        "• `/start` — Welcome screen\n"
        "• `/profile` — View your FEG Member Profile & Status\n"
        "• `/dashboard` — Interactive Member Dashboard\n"
        "• `/classic` — Join FEG Classic League & verify\n"
        "• `/h2h` — Join FEG H2H League & verify\n"
        "• `/cup` — Check FEG Cup status\n"
        "• `/cupstatus` — Poll live FPL Cup status\n"
        "• `/referral` — Personal referral link & milestone tracker\n"
        "• `/motw` — Manager of the Week info (starts GW4)\n"
        "• `/standings_classic` — Live Classic League standings\n"
        "• `/standings_h2h` — Live H2H League standings\n\n"
        "🏛️ **HALL OF FAME & CHAMPIONS:**\n"
        "• `/halloffame_classic` — Classic League Hall of Fame\n"
        "• `/halloffame_h2h` — H2H League Hall of Fame\n"
        "• `/halloffame_cup` — Knockout Cup Hall of Fame ('The Untouchable')\n"
        "• `/champion_classic` — Reigning Classic Champion\n"
        "• `/champion_h2h` — Reigning H2H Champion\n"
        "• `/champion_cup` — Reigning 'The Untouchable' Titleholder\n\n"
        "⚽ **FPL MEDIA & STATS:**\n"
        "• `/captain` — Captain recommendations\n"
        "• `/differentials` — Differential player picks\n"
        "• `/pricewatch` — Price rise & fall watch\n"
        "• `/preview` — Gameweek deadline preview\n"
        "• `/teamofgw` — View Team of the Gameweek graphic\n\n"
        "💡 *You can type any command or use the interactive buttons on your dashboard.*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def announcement_template_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📢 **FEG FPL 2026 — COMMUNITY WELCOME & MASTER ANNOUNCEMENT** 📌\n\n"
        "Welcome to **FEG FPL**, the premier paid Telegram Fantasy Premier League community and competition platform!\n\n"
        "🚀 **SEASON KICKOFF NOTICE:**\n"
        "• **Competition Start:** Official FEG League Scoring & Competitions officially kick off in **Gameweek 4**!\n"
        "• **Manager of the Week:** MOTW cash prize awards begin immediately at the conclusion of Gameweek 4 and continue after EVERY Gameweek!\n\n"
        "🏆 **FEG COMPETITIONS & PRIZE STRUCTURES:**\n"
        "• 👑 **Manager of the Week:** ₦1,000 Cash Prize awarded after EVERY Gameweek (starting GW4) to the top scoring manager in our Classic League!\n"
        "• 🏆 **Classic League Championship:** End-of-season cash prize pool for overall top rankers!\n"
        "• ⚔️ **Head-to-Head (H2H) League:** Weekly match battles with cash prizes for H2H season leaders starting GW4!\n"
        "• 🥊 **FEG Knockout Cup:** Pure prestige tournament! **No cash prize is awarded for the Cup** — instead, the winner is automatically crowned **'The Untouchable'** title, enshrined in the Hall of Fame, and carries the title into the following season!\n"
        "• 🏛️ **Hall of Fame:** Phase-by-phase stats breakdown (Early GW1–12, Mid GW13–26, Late GW27–38) recorded for every season champion!\n"
        "• 👥 **Referral Milestone Cash Rewards:**\n"
        "  - 3 Referrals ➡️ ₦2,000\n"
        "  - 5 Referrals ➡️ ₦4,000\n"
        "  - 7 Referrals ➡️ ₦6,000\n"
        "  - 10 Referrals ➡️ ₦10,000\n\n"
        "💳 **COMMUNITY REGISTRATION & ACCESS:**\n"
        "• **Registration Fee:** ₦5,000 (One-time payment for full season access)\n"
        "• **Payment Method:** Direct manual bank transfer with instant admin receipt review.\n"
        "• **Security & Privacy:** AES-256 encrypted bank payout accounts & single-use community access links.\n\n"
        "📌 **MEMBER COMMANDS DIRECTORY:**\n"
        "You can interact with our bot in private DM using these commands:\n\n"
        "👤 **PROFILE & DASHBOARDS:**\n"
        "• `/profile` or `/dashboard` — View your FEG Member Profile, FPL details & payout account.\n"
        "• `/info` — Inspect your registration status & referral stats.\n\n"
        "🏆 **LEAGUES & STANDINGS:**\n"
        "• `/classic` — Get FEG Classic League code & join link.\n"
        "• `/h2h` — Get FEG Head-to-Head League code & join link.\n"
        "• `/cup` — Check FEG Knockout Cup status & eligibility.\n"
        "• `/cupstatus` — Check live FPL Cup qualification threshold & status.\n"
        "• `/motw` — View Manager of the Week stats & top scores (starts GW4).\n"
        "• `/standings_classic` — Live top 10 Classic League standings.\n"
        "• `/standings_h2h` — Live top 10 H2H League standings & match records.\n\n"
        "🏛️ **HALL OF FAME & CHAMPIONS:**\n"
        "• `/halloffame_classic` — Classic League Hall of Fame history & phase breakdown.\n"
        "• `/halloffame_h2h` — Head-to-Head Hall of Fame history & phase breakdown.\n"
        "• `/halloffame_cup` — Knockout Cup Hall of Fame & 'The Untouchable' titleholders.\n"
        "• `/champion_classic` — Reigning Classic League Champion.\n"
        "• `/champion_h2h` — Reigning Head-to-Head Champion.\n"
        "• `/champion_cup` — Reigning 'The Untouchable' Cup Titleholder.\n\n"
        "👥 **REFERRALS & REWARDS:**\n"
        "• `/referral` — Get your personal referral link & track milestone earnings.\n\n"
        "⚽ **FPL CONTENT & MEDIA ENGINE:**\n"
        "• `/captain` — Weekly Captain recommendations based on FPL fixture metrics.\n"
        "• `/differentials` — Differential player picks under 10% ownership.\n"
        "• `/pricewatch` — Player price risers & fallers watch.\n"
        "• `/preview` — Gameweek preview & official FPL deadline reminders.\n"
        "• `/teamofgw` — Dynamic Team of the Gameweek high-resolution graphic.\n\n"
        "⚙️ **SYSTEM & HELP:**\n"
        "• `/help` — Full interactive commands & help menu.\n"
        "• `/health` — FEG system & database status report.\n\n"
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
