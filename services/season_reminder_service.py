import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from database.db import get_db_session
from database.models import User
from services.fpl_service import FPLService
from config.settings import settings
from config.logging_config import logger


class SeasonReminderService:
    @classmethod
    async def get_season_dates(cls) -> Dict[str, Any]:
        """
        Fetches dynamic FPL GW1 deadline from the FPL API and calculates:
        - gw1_deadline_dt: Official start of the Premier League season
        - purge_deadline_dt: 14 days (2 weeks) before GW1 start
        - reminder_start_dt: 21 days (3 weeks) before the purge deadline (35 days before GW1)
        """
        gw1_deadline_dt, source = await FPLService.get_season_start_deadline()

        purge_deadline_dt = gw1_deadline_dt - datetime.timedelta(days=14)
        reminder_start_dt = purge_deadline_dt - datetime.timedelta(days=21)

        return {
            "gw1_deadline_dt": gw1_deadline_dt,
            "purge_deadline_dt": purge_deadline_dt,
            "reminder_start_dt": reminder_start_dt,
            "source": source
        }

    @classmethod
    async def run_renewal_reminder_check(cls, bot, force: bool = False) -> Dict[str, Any]:
        """
        Checks if current time is within the 3-weeks-before-purge window (or if forced by admin),
        and sends an automated DM reminder to all members who have not renewed their membership.
        """
        dates = await cls.get_season_dates()
        purge_deadline_dt = dates["purge_deadline_dt"]
        reminder_start_dt = dates["reminder_start_dt"]

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        in_reminder_window = reminder_start_dt <= now_utc < purge_deadline_dt

        if not in_reminder_window and not force:
            logger.info(f"Renewal reminder check skipped. Current time ({now_utc.strftime('%Y-%m-%d')}) is outside 3-week pre-purge window ({reminder_start_dt.strftime('%Y-%m-%d')} to {purge_deadline_dt.strftime('%Y-%m-%d')}).")
            return {
                "sent_count": 0,
                "status": "SKIPPED_OUTSIDE_WINDOW",
                "purge_deadline": purge_deadline_dt.strftime("%Y-%m-%d %H:%M UTC")
            }

        sent_count = 0
        purge_fmt = purge_deadline_dt.strftime("%B %d, %Y at %H:%M UTC")

        async with get_db_session() as session:
            stmt = select(User).where(
                User.membership_status.in_(["ACTIVE", "PENDING_RENEWAL"]),
                User.renewal_payment_status != "APPROVED"
            )
            members = (await session.execute(stmt)).scalars().all()

            for member in members:
                if not member.telegram_id:
                    continue

                msg = (
                    "⏳ **UPCOMING SEASON MEMBERSHIP RENEWAL REMINDER** 🚨\n\n"
                    f"Hi **{member.full_name}**, this is an official automated reminder that your **FEG FPL Annual Membership Renewal** for the **{member.current_season or 'upcoming'}** season is due!\n\n"
                    f"📅 **Purge Deadline Date:** `{purge_fmt}`\n"
                    "*(Purge takes place exactly 2 weeks prior to the official start of the new FPL season)*\n\n"
                    "⚠️ **IMPORTANT:** Accounts not renewed prior to the purge deadline will be set to **EXPIRED** status.\n\n"
                    f"💳 **Annual Fee:** ₦{settings.FEG_REGISTRATION_FEE:,}\n\n"
                    "👉 **How to Renew:**\n"
                    "Transfer your annual fee to the FEG account and reply with your receipt screenshot by typing `/renew` in this chat!"
                )

                try:
                    await bot.send_message(
                        chat_id=member.telegram_id,
                        text=msg,
                        parse_mode="Markdown"
                    )
                    sent_count += 1
                except Exception as err:
                    logger.warning(f"Could not send renewal reminder DM to member {member.telegram_id} ({member.full_name}): {err}")

        logger.info(f"Automated renewal reminder DM sent to {sent_count} members.")
        return {
            "sent_count": sent_count,
            "status": "SUCCESS",
            "purge_deadline": purge_fmt
        }
