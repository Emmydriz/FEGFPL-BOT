import pytest
from database.db import get_db_session
from services.member_service import MemberService
from services.referral_service import ReferralService


@pytest.mark.asyncio
async def test_referral_tracking_and_milestone_evaluation():
    async with get_db_session() as session:
        # Create Referrer
        referrer = await MemberService.get_or_start_registration(
            session=session, telegram_id=11111111, full_name="Top Referrer"
        )
        referrer.registration_status = "APPROVED"
        await session.flush()

        # Create 3 referred members who get approved & paid
        for i in range(3):
            referred = await MemberService.get_or_start_registration(
                session=session, telegram_id=20000000 + i, full_name=f"Referred User {i+1}"
            )
            ref_rec = await ReferralService.record_referral(
                session=session,
                referrer_code=referrer.referral_code,
                new_user=referred
            )
            assert ref_rec is not None
            # Mark referred member as approved
            referred.registration_status = "APPROVED"
            await session.flush()

        count, reward_amt, reward_obj = await ReferralService.evaluate_referrals_and_rewards(
            session=session, referrer_user_id=referrer.id
        )

        assert count == 3
        assert reward_amt == 2000.0
        assert reward_obj is not None
        assert reward_obj.amount == 2000.0
        assert reward_obj.highest_milestone_count == 3

        # Add 2 more approved members (total 5)
        for i in range(3, 5):
            referred = await MemberService.get_or_start_registration(
                session=session, telegram_id=20000000 + i, full_name=f"Referred User {i+1}"
            )
            await ReferralService.record_referral(
                session=session,
                referrer_code=referrer.referral_code,
                new_user=referred
            )
            referred.registration_status = "APPROVED"
            await session.flush()

        count5, reward_amt5, reward_obj5 = await ReferralService.evaluate_referrals_and_rewards(
            session=session, referrer_user_id=referrer.id
        )

        assert count5 == 5
        assert reward_amt5 == 4000.0  # Highest milestone rule: upgraded to 4000
        assert reward_obj5.amount == 4000.0
        assert reward_obj5.highest_milestone_count == 5
