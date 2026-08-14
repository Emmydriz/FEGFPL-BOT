from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_member_start_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🚀 START REGISTRATION", callback_data="start_registration")],
        [InlineKeyboardButton("❓ HOW TO FIND MY FPL ID", callback_data="help_fpl_id")],
        [InlineKeyboardButton("💬 COMMUNITY SUPPORT", callback_data="support")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_super_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("👥 Members", callback_data="admin_members"), InlineKeyboardButton("💳 Payments", callback_data="admin_payments")],
        [InlineKeyboardButton("🏦 Payment Account", callback_data="admin_pay_account"), InlineKeyboardButton("🏆 Competitions", callback_data="admin_competitions")],
        [InlineKeyboardButton("⚽ FPL Engine", callback_data="admin_fpl_engine"), InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔥 Live Engine", callback_data="admin_live_engine"), InlineKeyboardButton("📰 Content Engine", callback_data="admin_content")],
        [InlineKeyboardButton("👥 Referrals", callback_data="admin_referrals"), InlineKeyboardButton("💰 Rewards", callback_data="admin_rewards")],
        [InlineKeyboardButton("📋 Records", callback_data="admin_records"), InlineKeyboardButton("🔍 Audit Logs", callback_data="admin_audit")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"), InlineKeyboardButton("🟢 System Health", callback_data="admin_health")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_finance_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("💳 PENDING PAYMENTS", callback_data="admin_payments_pending")],
        [InlineKeyboardButton("💰 PAYOUTS", callback_data="admin_payouts")],
        [InlineKeyboardButton("🏦 PAYMENT ACCOUNT", callback_data="admin_pay_account")],
        [InlineKeyboardButton("👥 MEMBERS", callback_data="admin_members")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_content_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📰 CONTENT ENGINE", callback_data="admin_content")],
        [InlineKeyboardButton("⚽ PLAYER STATS", callback_data="admin_stats")],
        [InlineKeyboardButton("🔥 LIVE MATCH", callback_data="admin_live_engine")],
        [InlineKeyboardButton("🎨 TEAM OF GW", callback_data="admin_team_gw")]
    ]
    return InlineKeyboardMarkup(keyboard)
