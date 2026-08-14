import datetime
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Referral, Reward
from config.settings import settings
from config.logging_config import logger


class ReferralService:
    @staticmethod
    def get_personal_referral_link(user: User) -> str:
        bot_username = settings.FEG_BOT_USERNAME.replace("@", "")
        return f"https://t.me/{bot_username}?start=ref_{user.referral_code}"

    @staticmethod
    async def record_referral(
        session: AsyncSession,
        referrer_code: str,
        new_user: User
    ) -> Optional[Referral]:
        stmt = select(User).where(User.referral_code == referrer_code)
        res = await session.execute(stmt)
        referrer = res.scalar_one_or_none()

        if not referrer or referrer.id == new_user.id:
            # Self-referral or invalid code rejected
            return None

        # Check duplicate
        stmt_ref = select(Referral).where(Referral.referred_user_id == new_user.id)
        res_ref = await session.execute(stmt_ref)
        if res_ref.scalar_one_or_none():
            return None

        referral = Referral(
            referrer_user_id=referrer.id,
            referred_user_id=new_user.id,
            status="PENDING"
        )
        session.add(referral)
        new_user.referred_by_id = referrer.id
        await session.flush()
        return referral

    @staticmethod
    async def evaluate_referrals_and_rewards(
        session: AsyncSession,
        referrer_user_id: int
    ) -> Tuple[int, float, Optional[Reward]]:
        """
        Calculates approved referrals for referrer and assigns reward based on highest milestone rule:
        - 3 refs -> ₦2,000
        - 5 refs -> ₦4,000
        - 7 refs -> ₦6,000
        - 10 refs -> ₦10,000
        Only the highest milestone achieved is paid.
        """
        # Count approved referred users who paid & have registration approved/community granted
        stmt = (
            select(func.count(Referral.id))
            .join(User, User.id == Referral.referred_user_id)
            .where(
                Referral.referrer_user_id == referrer_user_id,
                User.registration_status.in_(["APPROVED", "COMMUNITY_ACCESS_GRANTED"])
            )
        )
        res = await session.execute(stmt)
        approved_count = res.scalar() or 0

        # Milestone logic
        milestones = [
            (settings.REFERRAL_MILESTONE_4, float(settings.REFERRAL_REWARD_4)),  # 10 -> 10000
            (settings.REFERRAL_MILESTONE_3, float(settings.REFERRAL_REWARD_3)),  # 7 -> 6000
            (settings.REFERRAL_MILESTONE_2, float(settings.REFERRAL_REWARD_2)),  # 5 -> 4000
            (settings.REFERRAL_MILESTONE_1, float(settings.REFERRAL_REWARD_1)),  # 3 -> 2000
        ]

        target_milestone_count = 0
        eligible_reward_amount = 0.0

        for count_req, reward_amt in milestones:
            if approved_count >= count_req:
                target_milestone_count = count_req
                eligible_reward_amount = reward_amt
                break

        if eligible_reward_amount == 0.0:
            return approved_count, 0.0, None

        # Check existing highest milestone reward
        stmt_reward = (
            select(Reward)
            .where(
                Reward.user_id == referrer_user_id,
                Reward.reward_type == "REFERRAL_MILESTONE"
            )
            .order_by(Reward.highest_milestone_count.desc())
        )
        res_reward = await session.execute(stmt_reward)
        existing_reward = res_reward.scalar_one_or_none()

        if existing_reward:
            if existing_reward.highest_milestone_count >= target_milestone_count:
                # Already awarded this or higher milestone
                return approved_count, eligible_reward_amount, existing_reward
            else:
                # Upgrade existing reward to higher milestone amount
                existing_reward.amount = eligible_reward_amount
                existing_reward.highest_milestone_count = target_milestone_count
                await session.flush()
                return approved_count, eligible_reward_amount, existing_reward

        # Create new milestone reward record
        new_reward = Reward(
            user_id=referrer_user_id,
            reward_type="REFERRAL_MILESTONE",
            amount=eligible_reward_amount,
            highest_milestone_count=target_milestone_count,
            status="PENDING_APPROVAL"
        )
        session.add(new_reward)
        await session.flush()
        return approved_count, eligible_reward_amount, new_reward
