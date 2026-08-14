from telegram import Update
from telegram.ext import ContextTypes
from services.fpl_service import FPLService
from services.graphic_engine import GraphicEngine
from config.settings import settings


async def captain_picks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await FPLService.get_official_captain_picks()
    await update.message.reply_text(msg, parse_mode="Markdown")


async def differentials_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bootstrap = await FPLService.get_bootstrap_data()
    curr_gw = await FPLService.get_current_or_next_gameweek()
    gw_id = curr_gw.get("id", 1)

    if bootstrap:
        elements = bootstrap.get("elements", [])
        # Differentials: ownership < 10.0%, high form
        diffs = [p for p in elements if float(p.get("selected_by_percent", 100.0)) < 10.0]
        diffs = sorted(diffs, key=lambda x: float(x.get("form", 0.0)), reverse=True)[:3]

        lines = []
        for idx, p in enumerate(diffs, 1):
            cost = p.get("now_cost", 0) / 10.0
            lines.append(f"{idx}. **{p.get('web_name')}** — Ownership: {p.get('selected_by_percent')}% | Form: {p.get('form')} | Price: £{cost:.1f}m")

        msg = (
            f"💎 **OFFICIAL FPL DIFFERENTIAL PICKS — GAMEWEEK {gw_id}**\n\n"
            + "\n".join(lines) +
            "\n\nℹ️ *Note: Targeted differentials under 10% ownership to boost your FEG Classic & H2H rank.*"
        )
    else:
        msg = (
            f"💎 **DIFFERENTIAL PICKS — GAMEWEEK {gw_id}**\n\n"
            "1. **Bryan Mbeumo** (BRE) — Ownership: 7.4%\n"
            "2. **Dominic Solanke** (TOT) — Ownership: 8.1%\n"
            "3. **Antoine Semenyo** (BOU) — Ownership: 4.8%"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def price_watch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await FPLService.get_official_price_watch()
    await update.message.reply_text(msg, parse_mode="Markdown")


async def gw_preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    curr_gw = await FPLService.get_current_or_next_gameweek()
    gw_id = curr_gw.get("id", 1)
    deadline = curr_gw.get("deadline_time", "TBD")

    msg = (
        f"📋 **FEG FPL — GAMEWEEK {gw_id} PREVIEW**\n\n"
        f"⏰ **Official FPL Deadline:** `{deadline}`\n\n"
        "💡 **Strategy:**\n"
        "Verify your squad changes before the official FPL deadline.\n"
        "Make sure your team is joined inside the official FEG Classic & H2H leagues!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def team_of_gw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎨 Generating official Team of the Gameweek graphic from live FPL data...")

    gw_num, formation, players, total_points = await FPLService.get_official_team_of_gw()

    image_path = GraphicEngine.generate_team_of_gw_graphic(
        gameweek=gw_num,
        formation=formation,
        players=players,
        total_points=total_points
    )

    cap_name = "N/A"
    for p in players:
        if p.get("is_captain"):
            cap_name = p.get("name")
            break

    caption = (
        f"🎨 **FEG FPL — TEAM OF GAMEWEEK {gw_num}**\n\n"
        f"**Formation:** {formation}\n"
        f"**Total GW Points:** {total_points} PTS\n"
        f"**Captain:** {cap_name}\n\n"
        "ℹ️ *Official FPL Team of the Gameweek compiled directly from Fantasy Premier League scores.*"
    )

    with open(image_path, "rb") as photo_file:
        await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode="Markdown")
