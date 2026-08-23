from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_db_session
from services.hall_of_fame_service import HallOfFameService
from services.auth_service import admin_required, approved_member_required
from config.settings import settings
from config.logging_config import logger


async def _render_hall_of_fame_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    category_upper = category.upper()
    async with get_db_session() as session:
        from database.models import HallOfFameRecord
        from sqlalchemy import select
        stmt = select(HallOfFameRecord).where(HallOfFameRecord.category == category_upper).order_by(HallOfFameRecord.season.desc(), HallOfFameRecord.rank.asc())
        entries = (await session.execute(stmt)).scalars().all()

        if not entries:
            msg = (
                f"🏆 **FEG {category_upper} LEAGUE HALL OF FAME**\n\n"
                "No official Hall of Fame records logged yet.\n"
                "This is the inaugural season being tracked! Official winners for Classic, H2H, and Cup "
                "will be manually confirmed and permanently recorded by administrators at the end of the season."
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

        lines = [f"🏛️ **FEG {category_upper} LEAGUE HALL OF FAME** 👑\n"]
        for entry in entries:
            rank_medal = "🥇" if entry.rank == 1 else ("🥈" if entry.rank == 2 else "🥉")
            lines.append(
                f"**Season {entry.season}:** {rank_medal} **{entry.title}**\n"
                f"• **Manager:** {entry.manager_name} ({entry.team_name})\n"
                f"• **FEG Member ID:** `{entry.feg_member_id}`\n"
                f"• **Rank:** #{entry.rank}\n"
                f"• **Details:** {entry.details or 'Official Winner'}\n"
                "───────────────────────────"
            )

        msg = "\n\n".join(lines)
        await update.message.reply_text(msg, parse_mode="Markdown")


async def _render_champion_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    category_upper = category.upper()
    async with get_db_session() as session:
        champion = await HallOfFameService.get_latest_champion(session, category_upper)

        if not champion:
            if category_upper == "CLASSIC":
                msg = (
                    "🏆 **FEG CLASSIC LEAGUE REIGNING CHAMPION**\n\n"
                    "No Classic Champion crowned yet. The inaugural 2026/27 Classic League Champion "
                    "will be automatically crowned at season wrap!"
                )
            elif category_upper == "H2H":
                msg = (
                    "⚔️ **FEG HEAD-TO-HEAD REIGNING CHAMPION**\n\n"
                    "No H2H Champion crowned yet. The H2H Season Winner will be automatically inducted upon season conclusion!"
                )
            else:
                msg = (
                    "🥊 **FEG KNOCKOUT CUP REIGNING TITLEHOLDER**\n\n"
                    "No Cup Titleholder crowned yet!\n"
                    "The FEG Knockout Cup has not started. FPL automatically opens the Cup competition once our Classic League "
                    "meets FPL's required member count threshold.\n\n"
                    "💡 Use `/cupstatus` to check live qualification status!"
                )
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

        title_display = f"👑 **THE UNTOUCHABLE**" if champion.category == "CUP" else f"🏆 **{champion.title}**"
        msg = (
            f"👑 **FEG REIGNING CHAMPION — {category_upper}** 👑\n\n"
            f"• **Title:** {title_display}\n"
            f"• **Season:** {champion.season}\n"
            f"• **Manager:** {champion.manager_name}\n"
            f"• **Team Name:** {champion.team_name}\n"
            f"• **Season Total Points:** `{champion.total_points} PTS`\n\n"
            "📊 **SEASON PHASE PERFORMANCE:**\n"
            f"• **Early (GW1–12):** `{champion.early_phase_pts} PTS` (Best: `{champion.early_standout_gw}`)\n"
            f"• **Mid (GW13–26):** `{champion.mid_phase_pts} PTS` (Best: `{champion.mid_standout_gw}`)\n"
            f"• **Late (GW27–38):** `{champion.late_phase_pts} PTS` (Best: `{champion.late_standout_gw}`)"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


# General Routing Handlers
@approved_member_required()
async def hall_of_fame_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    category = args[0].upper() if args and args[0].lower() in ["classic", "h2h", "cup"] else "CLASSIC"
    await _render_hall_of_fame_category(update, context, category)


@approved_member_required()
async def champion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    category = args[0].upper() if args and args[0].lower() in ["classic", "h2h", "cup"] else "CLASSIC"
    await _render_champion_category(update, context, category)


# Specific Category Command Handlers
@approved_member_required()
async def hall_of_fame_classic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _render_hall_of_fame_category(update, context, "CLASSIC")


@approved_member_required()
async def hall_of_fame_h2h_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _render_hall_of_fame_category(update, context, "H2H")


@approved_member_required()
async def hall_of_fame_cup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _render_hall_of_fame_category(update, context, "CUP")


@approved_member_required()
async def champion_classic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _render_champion_category(update, context, "CLASSIC")


@approved_member_required()
async def champion_h2h_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _render_champion_category(update, context, "H2H")


@approved_member_required()
async def champion_cup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _render_champion_category(update, context, "CUP")


async def cup_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.handlers.dashboard import cup_dashboard_handler
    return await cup_dashboard_handler(update, context)


@admin_required()
async def finalize_season_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    season_str = args[0] if args else "2026/27"

    async with get_db_session() as session:
        entries = await HallOfFameService.finalize_season(session, season_str)
        await session.commit()

    msg = (
        f"✅ **SEASON {season_str} SUCCESSFULLY FINALIZED!** 🏆\n\n"
        "Automatically fetched winners from FPL API, computed phase statistics, and recorded entries:\n\n"
        f"• **Classic Champion:** {entries[0].manager_name} ({entries[0].total_points} PTS)\n"
        f"• **H2H Champion:** {entries[1].manager_name} ({entries[1].total_points} PTS)\n"
        f"• **Cup Champion:** {entries[2].manager_name} — Crowned **'The Untouchable'**! 👑\n\n"
        "Hall of Fame has been updated!"
    )

    if settings.FEG_COMMUNITY_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=settings.FEG_COMMUNITY_CHAT_ID,
                text=(
                    f"🎉 **FEG FPL SEASON {season_str} OFFICIAL WRAP & HALL OF FAME INDUCTION** 👑\n\n"
                    f"🏆 **Classic Champion:** {entries[0].manager_name} ({entries[0].team_name})\n"
                    f"⚔️ **H2H Champion:** {entries[1].manager_name} ({entries[1].team_name})\n"
                    f"🥊 **Cup Champion & 'The Untouchable':** {entries[2].manager_name} ({entries[2].team_name})!\n\n"
                    "Congratulations to all champions! Use `/halloffame_classic`, `/halloffame_h2h`, or `/halloffame_cup` in DM to view full stats!"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not post season finalization to community chat: {e}")

    await update.message.reply_text(msg, parse_mode="Markdown")


@admin_required()
async def add_winner_fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 6:
        await update.message.reply_text(
            "⚠️ **ADMIN FALLBACK ENTRY USAGE**\n\n"
            "Use `/addwinner Season | Category | FPL_ID | Title | ManagerName | TeamName`\n\n"
            "Example:\n"
            "`/addwinner 2026/27 | CLASSIC | 12345678 | Classic Champion | Emmanuel Ilesanmi | FEG Champions`",
            parse_mode="Markdown"
        )
        return

    raw_text = " ".join(args)
    parts = [p.strip() for p in raw_text.split("|")]
    if len(parts) < 6:
        await update.message.reply_text("⚠️ Invalid pipe-separated format.", parse_mode="Markdown")
        return

    season_str, category, fpl_id_str, title, manager_name, team_name = parts[:6]
    fpl_id = int(fpl_id_str) if fpl_id_str.isdigit() else 12345678

    async with get_db_session() as session:
        entry = await HallOfFameService.add_winner_fallback(
            session=session,
            season=season_str,
            category=category,
            fpl_id=fpl_id,
            manager_name=manager_name,
            team_name=team_name,
            title=title
        )
        await session.commit()

    await update.message.reply_text(
        f"✅ **HALL OF FAME ADMIN FALLBACK ENTRY RECORDED!**\n\n"
        f"• **Season:** {entry.season}\n"
        f"• **Category:** {entry.category}\n"
        f"• **Title:** {entry.title}\n"
        f"• **Manager:** {entry.manager_name} ({entry.team_name})\n"
        f"• **Phase Breakdown Calculated:** Early `{entry.early_phase_pts}` | Mid `{entry.mid_phase_pts}` | Late `{entry.late_phase_pts}`",
        parse_mode="Markdown"
    )
