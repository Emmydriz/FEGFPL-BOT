import pytest
from database.db import get_db_session
from database.models import HallOfFame
from services.hall_of_fame_service import HallOfFameService


@pytest.mark.asyncio
async def test_hall_of_fame_model():
    async with get_db_session() as session:
        entry = HallOfFame(
            season="2026/27",
            category="CUP",
            fpl_id=12345678,
            manager_name="Emmanuel Ilesanmi",
            team_name="FEG Champions",
            title="The Untouchable",
            total_points=2450,
            early_phase_pts=780,
            early_standout_gw="GW8 (89 PTS)",
            mid_phase_pts=920,
            mid_standout_gw="GW18 (96 PTS)",
            late_phase_pts=750,
            late_standout_gw="GW34 (112 PTS)"
        )
        session.add(entry)
        await session.commit()
        assert entry.id is not None
        assert entry.title == "The Untouchable"


@pytest.mark.asyncio
async def test_calculate_phase_stats():
    stats = await HallOfFameService.calculate_phase_stats(12345678)
    assert "early_phase_pts" in stats
    assert "mid_phase_pts" in stats
    assert "late_phase_pts" in stats
    assert "early_standout_gw" in stats


@pytest.mark.asyncio
async def test_poll_fpl_cup_status():
    status_info = await HallOfFameService.poll_fpl_cup_status()
    assert "status" in status_info
    assert "message" in status_info
    assert "has_cup" in status_info


@pytest.mark.asyncio
async def test_finalize_season():
    async with get_db_session() as session:
        entries = await HallOfFameService.finalize_season(session, "2026/27")
        await session.commit()
        assert len(entries) == 3

        classic_entry = await HallOfFameService.get_latest_champion(session, "CLASSIC")
        h2h_entry = await HallOfFameService.get_latest_champion(session, "H2H")
        cup_entry = await HallOfFameService.get_latest_champion(session, "CUP")

        assert classic_entry is not None
        assert h2h_entry is not None
        assert cup_entry is not None
        assert cup_entry.title == "The Untouchable"
