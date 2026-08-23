import pytest
from database.db import init_db, get_db_session
from database.models import User, HallOfFameRecord
from sqlalchemy import select
import datetime

@pytest.mark.asyncio
async def test_season_fields_and_hall_of_fame_records():
    await init_db()

    async with get_db_session() as session:
        # Create test user
        user = User(
            feg_member_id="FEG-2026-TEST01",
            telegram_id=999111222,
            full_name="Test Season User",
            registration_status="COMMUNITY_ACCESS_GRANTED",
            membership_status="ACTIVE",
            current_season="2026/2027",
            referral_code="FEG-REF-TEST01"
        )
        session.add(user)
        await session.flush()

        assert user.membership_status == "ACTIVE"
        assert user.current_season == "2026/2027"

        # Update to PENDING_RENEWAL
        user.membership_status = "PENDING_RENEWAL"
        user.renewal_deadline = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        await session.flush()

        assert user.membership_status == "PENDING_RENEWAL"

        # Soft delete to EXPIRED
        user.membership_status = "EXPIRED"
        await session.flush()

        assert user.membership_status == "EXPIRED"

        # Insert HallOfFameRecord
        hof = HallOfFameRecord(
            feg_member_id=user.feg_member_id,
            season="2026/2027",
            category="CLASSIC",
            rank=1,
            manager_name=user.full_name,
            team_name="Test FC",
            title="Classic Champion",
            details="Recorded by Admin"
        )
        session.add(hof)
        await session.commit()

    async with get_db_session() as session:
        stmt = select(HallOfFameRecord).where(HallOfFameRecord.feg_member_id == "FEG-2026-TEST01")
        res = (await session.execute(stmt)).scalar_one_or_none()

        assert res is not None
        assert res.rank == 1
        assert res.title == "Classic Champion"
