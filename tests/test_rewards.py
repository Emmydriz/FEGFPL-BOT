import pytest
from sqlalchemy import select
from database.db import get_db_session
from database.models import AuditLog
from services.member_service import MemberService
from services.reward_service import RewardService


@pytest.mark.asyncio
async def test_manager_of_week_and_reward_payout():
    async with get_db_session() as session:
        user = await MemberService.get_or_start_registration(
            session=session, telegram_id=77777777, full_name="GW Winner"
        )
        payout_acc = await MemberService.save_payout_account(
            session=session,
            user=user,
            bank_name="GTBank",
            account_name="GW Winner",
            account_number="0987654321"
        )

        reward = await RewardService.create_manager_of_week_reward(
            session=session,
            user_id=user.id,
            gameweek=7,
            amount=1000.0
        )
        assert reward.amount == 1000.0
        assert reward.status == "PENDING_APPROVAL"

        # Mark paid by admin
        success, paid_reward = await RewardService.mark_reward_paid(
            session=session,
            reward_id=reward.id,
            admin_id=123456789,
            admin_role="SUPER_ADMIN",
            payment_reference="REF_BANK_12345"
        )
        assert success is True
        assert paid_reward.status == "PAID"
        assert paid_reward.payment_reference == "REF_BANK_12345"

        stmt = select(AuditLog).where(AuditLog.action == "PAID_REWARD")
        res = await session.execute(stmt)
        audit = res.scalar_one_or_none()
        assert audit is not None
        assert audit.admin_id == 123456789
