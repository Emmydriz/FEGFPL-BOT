import os
import sys

# Add project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from telegram import BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    MessageHandler,
    filters
)
from config.settings import settings
from config.logging_config import logger
from database.db import init_db
from bot.handlers.common import (
    start_handler,
    help_handler,
    health_handler,
    chat_id_handler,
    announcement_template_handler
)
from bot.handlers.admin import (
    admin_dashboard_handler,
    admin_payment_account_handler,
    admin_set_payment_account_handler,
    admin_pending_payments_handler,
    admin_generic_callback,
    search_member_admin_handler,
    admin_referrals_tracker_handler,
    announce_gw_winner_handler,
    admin_members_list_handler,
    admin_audit_logs_handler,
    view_member_detail_callback,
    admin_update_member_handler,
    get_admin_update_account_conversation_handler,
    admin_start_new_season_handler,
    admin_purge_unrenewed_handler,
    admin_confirm_purge_callback,
    admin_record_hall_of_fame_handler,
    admin_trigger_renewal_reminders_handler,
    export_members_admin_handler,
    admin_import_forwarded_message_handler,
    restore_member_command_handler
)
from bot.handlers.hall_of_fame import (
    hall_of_fame_handler,
    hall_of_fame_classic_handler,
    hall_of_fame_h2h_handler,
    hall_of_fame_cup_handler,
    champion_handler,
    champion_classic_handler,
    champion_h2h_handler,
    champion_cup_handler,
    cup_status_handler,
    finalize_season_handler,
    add_winner_fallback_handler
)
from bot.handlers.register import (
    get_registration_conversation_handler,
    show_payment_details_handler
)
from bot.handlers.payment_admin import (
    admin_approve_payment_callback,
    admin_reject_payment_callback,
    admin_approve_renewal_callback,
    admin_reject_renewal_callback
)
from bot.handlers.dashboard import (
    member_profile_dashboard_handler,
    classic_dashboard_handler,
    h2h_dashboard_handler,
    cup_dashboard_handler,
    verify_membership_callback,
    standings_classic_handler,
    standings_h2h_handler,
    motw_handler,
    set_name_handler,
    set_fpl_handler,
    set_bank_handler
)
from bot.handlers.content import (
    captain_picks_handler,
    differentials_handler,
    price_watch_handler,
    gw_preview_handler,
    team_of_gw_handler
)
from services.community_service import welcome_new_member_handler


async def post_init(application):
    logger.info("Initializing database tables...")
    await init_db()
    logger.info("Database initialized successfully.")

    try:
        from services.seed_service import auto_seed_production_users
        await auto_seed_production_users()
    except Exception as e:
        logger.warning(f"Production auto-seed warning: {e}")

    try:
        import asyncio
        from services.season_reminder_service import SeasonReminderService
        asyncio.create_task(SeasonReminderService.run_renewal_reminder_check(bot=application.bot))
    except Exception as e:
        logger.warning(f"Season renewal reminder check warning: {e}")

    # Register Bot Commands for Telegram UI Menu
    commands = [
        BotCommand("start", "Welcome screen & start registration"),
        BotCommand("help", "Commands directory & help"),
        BotCommand("profile", "View member profile & status"),
        BotCommand("dashboard", "Interactive member dashboard"),
        BotCommand("classic", "FEG Classic League joining info"),
        BotCommand("h2h", "FEG Head-to-Head League joining info"),
        BotCommand("cup", "FEG Cup status & eligibility"),
        BotCommand("cupstatus", "Poll live FPL Cup status"),
        BotCommand("halloffame_classic", "Classic League Hall of Fame"),
        BotCommand("halloffame_h2h", "H2H League Hall of Fame"),
        BotCommand("halloffame_cup", "Knockout Cup Hall of Fame"),
        BotCommand("champion_classic", "Classic Reigning Champion"),
        BotCommand("champion_h2h", "H2H Reigning Champion"),
        BotCommand("champion_cup", "The Untouchable Cup Titleholder"),
        BotCommand("referral", "Personal referral link & rewards"),
        BotCommand("renew", "Submit annual membership renewal proof"),
        BotCommand("motw", "Manager of the Week info (starts GW4)"),
        BotCommand("standings_classic", "Live Classic League standings"),
        BotCommand("standings_h2h", "Live H2H League standings"),
        BotCommand("captain", "Captain recommendations"),
        BotCommand("differentials", "Differential player picks"),
        BotCommand("pricewatch", "Player price rise & fall watch"),
        BotCommand("preview", "Gameweek deadline preview"),
        BotCommand("teamofgw", "Team of the Gameweek graphic"),
        BotCommand("health", "System health diagnostic report"),
        BotCommand("id", "Display Chat/User ID"),
        BotCommand("payments", "Review pending payments (Admin)"),
        BotCommand("members", "Browse community members (Admin)"),
        BotCommand("search_member", "Inspect member details (Admin)"),
        BotCommand("updateaccount", "Update member bank account details (Admin)"),
        BotCommand("start_new_season", "Initialize new season & deadlines (Admin)"),
        BotCommand("purge_unrenewed", "Purge unrenewed members (Admin)"),
        BotCommand("record_hall_of_fame", "Record permanent season winner (Admin)"),
        BotCommand("admin_referrals", "Referral leaderboard (Admin)"),
        BotCommand("finalizeseason", "Automated FPL season wrap (Admin)"),
        BotCommand("addwinner", "Admin fallback winner record"),
        BotCommand("announce_gw_winner", "Announce GW winner (Admin)"),
        BotCommand("announcement_template", "Pinned channel message template"),
        BotCommand("admin", "Admin Dashboard (Authorized Admins)")
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Registered Telegram UI bot command menu.")
    except Exception as e:
        logger.warning(f"Could not register Telegram UI bot commands: {e}")


def build_app():
    if not settings.BOT_TOKEN or settings.BOT_TOKEN.startswith("123456789:ABCdef"):
        logger.warning("Using default or mock BOT_TOKEN. Set BOT_TOKEN in .env for live Telegram connection.")

    app = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Community New Member Join Handler
    app.add_handler(ChatMemberHandler(welcome_new_member_handler, ChatMemberHandler.CHAT_MEMBER))

    # Registration Conversation Handler
    app.add_handler(get_registration_conversation_handler())

    # Admin Update Account Conversation Handler
    app.add_handler(get_admin_update_account_conversation_handler())

    # Common & Member Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("health", health_handler))
    app.add_handler(CommandHandler("id", chat_id_handler))
    app.add_handler(CommandHandler("pay", show_payment_details_handler))
    app.add_handler(CommandHandler("payment", show_payment_details_handler))
    app.add_handler(CommandHandler("announcement_template", announcement_template_handler))

    # Member Dashboard & Standings Commands
    app.add_handler(CommandHandler("profile", member_profile_dashboard_handler))
    app.add_handler(CommandHandler("dashboard", member_profile_dashboard_handler))
    app.add_handler(CommandHandler("referral", member_profile_dashboard_handler))
    app.add_handler(CommandHandler("setname", set_name_handler))
    app.add_handler(CommandHandler("setfpl", set_fpl_handler))
    app.add_handler(CommandHandler("setbank", set_bank_handler))
    app.add_handler(CommandHandler("classic", classic_dashboard_handler))
    app.add_handler(CommandHandler("h2h", h2h_dashboard_handler))
    app.add_handler(CommandHandler("cup", cup_dashboard_handler))
    app.add_handler(CommandHandler("cupstatus", cup_status_handler))
    app.add_handler(CommandHandler("cup_status", cup_status_handler))

    # Hall of Fame Commands (Per League Category)
    app.add_handler(CommandHandler("halloffame_classic", hall_of_fame_classic_handler))
    app.add_handler(CommandHandler("classic_halloffame", hall_of_fame_classic_handler))
    app.add_handler(CommandHandler("halloffame_h2h", hall_of_fame_h2h_handler))
    app.add_handler(CommandHandler("h2h_halloffame", hall_of_fame_h2h_handler))
    app.add_handler(CommandHandler("halloffame_cup", hall_of_fame_cup_handler))
    app.add_handler(CommandHandler("cup_halloffame", hall_of_fame_cup_handler))
    app.add_handler(CommandHandler("halloffame", hall_of_fame_handler))
    app.add_handler(CommandHandler("hall_of_fame", hall_of_fame_handler))

    # Reigning Champion Commands (Per League Category)
    app.add_handler(CommandHandler("champion_classic", champion_classic_handler))
    app.add_handler(CommandHandler("classic_champion", champion_classic_handler))
    app.add_handler(CommandHandler("champion_h2h", champion_h2h_handler))
    app.add_handler(CommandHandler("h2h_champion", champion_h2h_handler))
    app.add_handler(CommandHandler("champion_cup", champion_cup_handler))
    app.add_handler(CommandHandler("cup_champion", champion_cup_handler))
    app.add_handler(CommandHandler("champion", champion_handler))
    app.add_handler(CommandHandler("champions", champion_handler))

    # Gameweek & Media Commands
    app.add_handler(CommandHandler("motw", motw_handler))
    app.add_handler(CommandHandler("standings_classic", standings_classic_handler))
    app.add_handler(CommandHandler("classic_standings", standings_classic_handler))
    app.add_handler(CommandHandler("standings_h2h", standings_h2h_handler))
    app.add_handler(CommandHandler("h2h_standings", standings_h2h_handler))
    app.add_handler(CommandHandler("captain", captain_picks_handler))
    app.add_handler(CommandHandler("differentials", differentials_handler))
    app.add_handler(CommandHandler("pricewatch", price_watch_handler))
    app.add_handler(CommandHandler("preview", gw_preview_handler))
    app.add_handler(CommandHandler("teamofgw", team_of_gw_handler))

    # Admin Commands
    app.add_handler(CommandHandler("admin", admin_dashboard_handler))
    app.add_handler(CommandHandler("pending", admin_pending_payments_handler))
    app.add_handler(CommandHandler("payments", admin_pending_payments_handler))
    app.add_handler(CommandHandler("pending_payments", admin_pending_payments_handler))
    app.add_handler(CommandHandler("members", admin_members_list_handler))
    app.add_handler(CommandHandler("set_pay_account", admin_set_payment_account_handler))
    app.add_handler(CommandHandler("search_member", search_member_admin_handler))
    app.add_handler(CommandHandler("member", search_member_admin_handler))
    app.add_handler(CommandHandler("admin_update_member", admin_update_member_handler))
    app.add_handler(CommandHandler("update_member", admin_update_member_handler))
    app.add_handler(CommandHandler("start_new_season", admin_start_new_season_handler))
    app.add_handler(CommandHandler("purge_unrenewed", admin_purge_unrenewed_handler))
    app.add_handler(CommandHandler("record_hall_of_fame", admin_record_hall_of_fame_handler))
    app.add_handler(CommandHandler("add_hof", admin_record_hall_of_fame_handler))
    app.add_handler(CommandHandler("trigger_renewal_reminders", admin_trigger_renewal_reminders_handler))
    app.add_handler(CommandHandler("send_reminders", admin_trigger_renewal_reminders_handler))
    app.add_handler(CommandHandler("restore_member", restore_member_command_handler))
    app.add_handler(CommandHandler("restore_profile", restore_member_command_handler))
    app.add_handler(CommandHandler("export_members", export_members_admin_handler))
    app.add_handler(CommandHandler("export", export_members_admin_handler))
    app.add_handler(CommandHandler("admin_referrals", admin_referrals_tracker_handler))
    app.add_handler(CommandHandler("audit_logs", admin_audit_logs_handler))
    app.add_handler(CommandHandler("auditlogs", admin_audit_logs_handler))
    app.add_handler(CommandHandler("finalizeseason", finalize_season_handler))
    app.add_handler(CommandHandler("finalize_season", finalize_season_handler))
    app.add_handler(CommandHandler("addwinner", add_winner_fallback_handler))
    app.add_handler(CommandHandler("add_winner", add_winner_fallback_handler))
    app.add_handler(CommandHandler("announce_gw_winner", announce_gw_winner_handler))
    app.add_handler(MessageHandler((filters.FORWARDED | filters.TEXT | filters.CAPTION) & ~filters.COMMAND, admin_import_forwarded_message_handler))

    # Payment Approval & Rejection Callbacks
    app.add_handler(CallbackQueryHandler(admin_approve_payment_callback, pattern="^approve_pay_"))
    app.add_handler(CallbackQueryHandler(admin_reject_payment_callback, pattern="^reject_pay_"))
    app.add_handler(CallbackQueryHandler(admin_approve_renewal_callback, pattern="^approve_ren_"))
    app.add_handler(CallbackQueryHandler(admin_reject_renewal_callback, pattern="^reject_ren_"))
    app.add_handler(CallbackQueryHandler(admin_confirm_purge_callback, pattern="^(confirm_purge_unrenewed|cancel_purge_unrenewed)$"))

    # Admin Dashboard Callbacks
    app.add_handler(CallbackQueryHandler(admin_payment_account_handler, pattern="^admin_pay_account$"))
    app.add_handler(CallbackQueryHandler(view_member_detail_callback, pattern="^view_member_"))
    app.add_handler(CallbackQueryHandler(admin_generic_callback, pattern="^admin_"))

    # Member Dashboard Callbacks
    app.add_handler(CallbackQueryHandler(classic_dashboard_handler, pattern="^view_classic$"))
    app.add_handler(CallbackQueryHandler(h2h_dashboard_handler, pattern="^view_h2h$"))
    app.add_handler(CallbackQueryHandler(cup_dashboard_handler, pattern="^view_cup$"))
    app.add_handler(CallbackQueryHandler(member_profile_dashboard_handler, pattern="^view_referrals$"))
    app.add_handler(CallbackQueryHandler(verify_membership_callback, pattern="^verify_"))
    app.add_handler(CallbackQueryHandler(standings_classic_handler, pattern="^view_classic_standings$"))
    app.add_handler(CallbackQueryHandler(standings_h2h_handler, pattern="^view_h2h_standings$"))

    return app


def main():
    logger.info("Starting FEG FPL Telegram Bot Core...")
    app = build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
