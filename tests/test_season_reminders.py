import pytest
import datetime
from database.db import init_db, get_db_session
from database.models import User
from services.season_reminder_service import SeasonReminderService

@pytest.mark.asyncio
async def test_season_reminder_service_dates():
    dates = await SeasonReminderService.get_season_dates()
    
    assert "gw1_deadline_dt" in dates
    assert "purge_deadline_dt" in dates
    assert "reminder_start_dt" in dates
    
    # Verify exact 14 days and 21 days math
    assert (dates["gw1_deadline_dt"] - dates["purge_deadline_dt"]).days == 14
    assert (dates["purge_deadline_dt"] - dates["reminder_start_dt"]).days == 21

@pytest.mark.asyncio
async def test_season_reminder_check_run():
    await init_db()
    class MockBot:
        def __init__(self):
            self.sent_messages = []
        async def send_message(self, chat_id, text, parse_mode=None):
            self.sent_messages.append({"chat_id": chat_id, "text": text})

    mock_bot = MockBot()
    res = await SeasonReminderService.run_renewal_reminder_check(bot=mock_bot, force=True)
    
    assert res["status"] == "SUCCESS"
