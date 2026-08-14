import datetime
from typing import Optional, Tuple, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Reward, PayoutAccount
from database.crypto import decrypt_string, mask_account_number
from database.repository import add_audit_log


class RewardService:
    @staticmethod
    async def create_manager_of_week_reward(
        session: AsyncSession,
        user_id: int,
        gameweek: int,
        amount: float = 1000.0
    ) -> Reward:
        reward = Reward(
            user_id=user_id,
            reward_type="MANAGER_OF_WEEK",
            gameweek=gameweek,
            amount=amount,
            status="PENDING_APPROVAL"
        )
        session.add(reward)
        await session.flush()
        return reward

    @staticmethod
    async def get_reward_payout_details(
        session: AsyncSession,
        reward_id: int
    ) -> Tuple[Optional[Reward], Optional[User], Optional[PayoutAccount]]:
        stmt = select(Reward).where(Reward.id == reward_id)
        res = await session.execute(stmt)
        reward = res.scalar_one_or_none()

        if not reward:
            return None, None, None

        stmt_user = select(User).where(User.id == reward.user_id)
        res_u = await session.execute(stmt_user)
        user = res_u.scalar_one_or_none()

        stmt_pay = select(PayoutAccount).where(PayoutAccount.user_id == reward.user_id)
        res_p = await session.execute(stmt_pay)
        payout_account = res_p.scalar_one_or_none()

        return reward, user, payout_account

    @staticmethod
    async def mark_reward_paid(
        session: AsyncSession,
        reward_id: int,
        admin_id: int,
        admin_role: str,
        payment_reference: str
    ) -> Tuple[bool, Optional[Reward]]:
        stmt = select(Reward).where(Reward.id == reward_id)
        res = await session.execute(stmt)
        reward = res.scalar_one_or_none()

        if not reward:
            return False, None

        reward.status = "PAID"
        reward.approved_by_admin_id = admin_id
        reward.paid_at = datetime.datetime.now(datetime.timezone.utc)
        reward.payment_reference = payment_reference

        await add_audit_log(
            session=session,
            admin_id=admin_id,
            role=admin_role,
            action="PAID_REWARD",
            target=f"Reward ID {reward.id}",
            details=f"Marked reward ID {reward.id} of amount ₦{reward.amount} as PAID. Reference: {payment_reference}"
        )

        await session.flush()
        return True, reward
