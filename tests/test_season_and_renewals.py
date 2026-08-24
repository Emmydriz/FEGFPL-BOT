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


@pytest.mark.asyncio
async def test_dynamic_season_purge_date():
    from services.fpl_service import FPLService
    from services.season_reminder_service import SeasonReminderService

    # Test dynamic FPL API season deadline fetch
    gw1_dt, source = await FPLService.get_season_start_deadline()
    assert gw1_dt is not None
    assert isinstance(gw1_dt, datetime.datetime)

    dates = await SeasonReminderService.get_season_dates()
    purge_dt = dates["purge_deadline_dt"]
    reminder_dt = dates["reminder_start_dt"]

    # Verify purge date is exactly 14 days before GW1 deadline
    assert purge_dt == gw1_dt - datetime.timedelta(days=14)

    # Verify reminder date is 21 days before purge date (35 days before GW1)
    assert reminder_dt == purge_dt - datetime.timedelta(days=21)
