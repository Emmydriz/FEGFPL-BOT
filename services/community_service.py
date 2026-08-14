import datetime
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, CommunityInvite
from database.db import get_db_session
from config.settings import settings
from config.logging_config import logger
from telegram import Update, ChatMember
from telegram.ext import ContextTypes


class CommunityService:
    @staticmethod
    async def create_one_time_invite(
        session: AsyncSession,
        user: User,
        bot=None
    ) -> CommunityInvite:
        invite_link = settings.FEG_COMMUNITY_INVITE_LINK or f"https://t.me/+feg_invite_{user.feg_member_id}"
        invite_link_id = f"link_{user.feg_member_id}"

        if bot and settings.FEG_COMMUNITY_CHAT_ID:
            try:
                expire_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=48)
                chat_invite = await bot.create_chat_invite_link(
                    chat_id=settings.FEG_COMMUNITY_CHAT_ID,
                    name=f"FEG Member {user.feg_member_id} ({user.full_name[:15]})",
                    expire_date=expire_dt,
                    member_limit=1
                )
                invite_link = chat_invite.invite_link
                invite_link_id = chat_invite.invite_link
                logger.info(f"Generated fresh single-use Telegram group invite link for User {user.id}: {invite_link}")
            except Exception as e:
                logger.warning(f"Could not generate live Telegram single-use invite link: {e}. Using configured link: {invite_link}")

        invite = CommunityInvite(
            user_id=user.id,
            invite_link=invite_link,
            invite_link_id=invite_link_id,
            status="ACTIVE"
        )
        session.add(invite)
        user.registration_status = "COMMUNITY_ACCESS_GRANTED"
        await session.flush()
        return invite


async def welcome_new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    if old_status not in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER] and new_status == ChatMember.MEMBER:
        user = result.new_chat_member.user
        display_name = user.full_name or user.username or "FPL Manager"

        # Update member registration status to COMMUNITY_ACCESS_GRANTED in database
        try:
            async with get_db_session() as session:
                stmt = select(User).where(User.telegram_id == user.id)
                db_user = (await session.execute(stmt)).scalar_one_or_none()
                if db_user:
                    db_user.registration_status = "COMMUNITY_ACCESS_GRANTED"
                    await session.commit()
                    logger.info(f"Updated status for member {db_user.feg_member_id} ({user.id}) to COMMUNITY_ACCESS_GRANTED upon joining chat.")
        except Exception as err:
            logger.error(f"Error updating member status on chat join: {err}")

        # Send public welcome message in General Community Chat
        welcome_text = (
            f"🎉 **WELCOME TO THE OFFICIAL FEG FPL COMMUNITY!** ⚽\n\n"
            f"Welcome **{display_name}** (@{user.username or 'NoUsername'})!\n"
            "We are thrilled to have you in our paid FPL community.\n\n"
            "📌 **COMMUNITY QUICK GUIDE:**\n"
            "• Join the banter & live match discussions during Gameweeks.\n"
            "• Check your personal stats, league codes, & referral link via DM with @FEGFPL_Bot.\n"
            "• Official FEG League Scoring & MOTW (₦1,000 cash prize) kick off in Gameweek 4!\n"
            "• Use `/help` in DM for all available member commands."
        )
        try:
            await context.bot.send_message(
                chat_id=result.chat.id,
                text=welcome_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not send welcome message to community chat {result.chat.id}: {e}")

        # Direct DM welcome to member
        member_dm_text = (
            f"🎉 **WELCOME TO FEG FPL COMMUNITY!** ⚽\n\n"
            f"Hi **{display_name}**, your community access has been verified!\n\n"
            "📌 **IMPORTANT REMINDERS:**\n"
            "• **Kickoff:** Official FEG competition scoring starts in **Gameweek 4**.\n"
            "• **Classic & H2H Leagues:** Make sure you join both leagues via `/classic` and `/h2h`.\n"
            "• **Manager of the Week:** ₦1,000 cash prizes begin immediately after Gameweek 4.\n"
            "• **Referral Rewards:** Share your referral link via `/referral` to earn up to ₦10,000!\n\n"
            "Type `/profile` or `/dashboard` anytime to check your stats."
        )
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=member_dm_text,
                parse_mode="Markdown"
            )
        except Exception as dm_err:
            logger.warning(f"Could not send direct welcome DM to user {user.id}: {dm_err}")
