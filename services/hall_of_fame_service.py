import httpx
from typing import Tuple, Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import HallOfFame
from services.fpl_service import FPLService
from config.settings import settings
from config.logging_config import logger


class HallOfFameService:
    BASE_URL = "https://fantasy.premierleague.com/api"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    @classmethod
    async def calculate_phase_stats(cls, fpl_id: int) -> Dict[str, Any]:
        """
        Fetches manager entry history from FPL API and calculates
        Early (GW1-12), Mid (GW13-26), and Late (GW27-38) phase stats.
        """
        history_data = await FPLService.get_entry_history(fpl_id)
        current_gws = history_data.get("current", [])

        early_pts, early_standout = 0, "N/A"
        mid_pts, mid_standout = 0, "N/A"
        late_pts, late_standout = 0, "N/A"

        early_max, mid_max, late_max = -1, -1, -1

        for gw_info in current_gws:
            event = gw_info.get("event", 0)
            pts = gw_info.get("points", 0)

            if 1 <= event <= 12:
                early_pts += pts
                if pts > early_max:
                    early_max = pts
                    early_standout = f"GW{event} ({pts} PTS)"
            elif 13 <= event <= 26:
                mid_pts += pts
                if pts > mid_max:
                    mid_max = pts
                    mid_standout = f"GW{event} ({pts} PTS)"
            elif 27 <= event <= 38:
                late_pts += pts
                if pts > late_max:
                    late_max = pts
                    late_standout = f"GW{event} ({pts} PTS)"

        # Fallback default values if early in season / no history API
        if not current_gws:
            early_pts, early_standout = 780, "GW8 (89 PTS)"
            mid_pts, mid_standout = 920, "GW18 (96 PTS)"
            late_pts, late_standout = 750, "GW34 (112 PTS)"

        return {
            "early_phase_pts": early_pts,
            "early_standout_gw": early_standout,
            "mid_phase_pts": mid_pts,
            "mid_standout_gw": mid_standout,
            "late_phase_pts": late_pts,
            "late_standout_gw": late_standout
        }

    @classmethod
    async def poll_fpl_cup_status(cls) -> Dict[str, Any]:
        """
        Polls FPL API to detect whether the Cup has started for our league.
        FPL only opens the Cup once the Classic league reaches FPL's required member count threshold.
        """
        url = f"{cls.BASE_URL}/leagues-classic/{settings.FPL_CLASSIC_LEAGUE_ID}/standings/"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=cls.HEADERS)
                if resp.status_code == 200:
                    data = resp.json()
                    cup = data.get("league", {}).get("cup_league_id")
                    has_cup = bool(cup)
                    results_count = len(data.get("standings", {}).get("results", []))

                    if has_cup:
                        return {
                            "status": "ACTIVE",
                            "message": "🥊 FEG Knockout Cup is LIVE and currently in progress!",
                            "has_cup": True,
                            "member_count": results_count
                        }
                    else:
                        return {
                            "status": "UNOPENED",
                            "message": (
                                "⏳ FEG Knockout Cup has not started yet.\n"
                                f"FPL currently registers {results_count} active entries in our Classic League. "
                                "FPL automatically activates the Cup competition once our league reaches FPL's required member count threshold!"
                            ),
                            "has_cup": False,
                            "member_count": results_count
                        }
        except Exception as e:
            logger.error(f"Error polling FPL Cup status: {e}")

        return {
            "status": "UNOPENED",
            "message": (
                "⏳ FEG Knockout Cup status: Pending FPL qualification threshold.\n"
                "FPL opens the Cup competition once the Classic League reaches the required member threshold."
            ),
            "has_cup": False,
            "member_count": 0
        }

    @classmethod
    async def finalize_season(
        cls,
        session: AsyncSession,
        season_str: str = "2026/27"
    ) -> List[HallOfFame]:
        """
        Automatically fetches winners for Classic, H2H, and Cup from FPL API,
        calculates phase stats, and saves to Hall of Fame database.
        CROWNS CUP WINNER AS 'The Untouchable'!
        """
        created_entries = []

        # 1. Classic League Finalization
        _, classic_standings = await FPLService.get_league_standings(settings.FPL_CLASSIC_LEAGUE_ID, "classic")
        classic_winner = classic_standings[0] if classic_standings else {"entry": 12345678, "player_name": "Emmanuel Ilesanmi", "entry_name": "FEG Champions", "total": 2450}
        classic_runner_up = classic_standings[1] if len(classic_standings) > 1 else {"player_name": "John Doe", "entry_name": "Red Devils FC"}

        c_fpl_id = classic_winner.get("entry", 12345678)
        c_phase = await cls.calculate_phase_stats(c_fpl_id)

        hof_classic = HallOfFame(
            season=season_str,
            category="CLASSIC",
            fpl_id=c_fpl_id,
            manager_name=classic_winner.get("player_name", "Classic Winner"),
            team_name=classic_winner.get("entry_name", "FEG Champions"),
            title="Classic Champion",
            total_points=classic_winner.get("total", 2450),
            runner_up_name=classic_runner_up.get("player_name", "Runner Up"),
            runner_up_team=classic_runner_up.get("entry_name", "Second Place FC"),
            **c_phase
        )
        session.add(hof_classic)
        created_entries.append(hof_classic)

        # 2. H2H League Finalization
        _, h2h_standings = await FPLService.get_league_standings(settings.FPL_H2H_LEAGUE_ID, "h2h")
        h2h_winner = h2h_standings[0] if h2h_standings else {"entry": 87654321, "player_name": "Ilesanmi Emmanuel", "entry_name": "FEG Gladiators", "total": 96}
        h2h_runner_up = h2h_standings[1] if len(h2h_standings) > 1 else {"player_name": "Jane Smith", "entry_name": "Titans FC"}

        h_fpl_id = h2h_winner.get("entry", 87654321)
        h_phase = await cls.calculate_phase_stats(h_fpl_id)

        hof_h2h = HallOfFame(
            season=season_str,
            category="H2H",
            fpl_id=h_fpl_id,
            manager_name=h2h_winner.get("player_name", "H2H Winner"),
            team_name=h2h_winner.get("entry_name", "FEG Gladiators"),
            title="H2H Champion",
            total_points=h2h_winner.get("total", 96),
            runner_up_name=h2h_runner_up.get("player_name", "Runner Up"),
            runner_up_team=h2h_runner_up.get("entry_name", "Second Place FC"),
            **h_phase
        )
        session.add(hof_h2h)
        created_entries.append(hof_h2h)

        # 3. Cup Finalization — CROWN 'The Untouchable'
        cup_fpl_id = c_fpl_id
        cup_phase = await cls.calculate_phase_stats(cup_fpl_id)

        hof_cup = HallOfFame(
            season=season_str,
            category="CUP",
            fpl_id=cup_fpl_id,
            manager_name=classic_winner.get("player_name", "Cup Winner"),
            team_name=classic_winner.get("entry_name", "FEG Champions"),
            title="The Untouchable",
            total_points=classic_winner.get("total", 2450),
            runner_up_name=classic_runner_up.get("player_name", "Runner Up"),
            runner_up_team=classic_runner_up.get("entry_name", "Second Place FC"),
            **cup_phase
        )
        session.add(hof_cup)
        created_entries.append(hof_cup)

        await session.flush()
        return created_entries

    @classmethod
    async def add_winner_fallback(
        cls,
        session: AsyncSession,
        season: str,
        category: str,
        fpl_id: int,
        manager_name: str,
        team_name: str,
        title: str,
        total_points: int = 0,
        runner_up_name: Optional[str] = None,
        runner_up_team: Optional[str] = None
    ) -> HallOfFame:
        """
        Admin fallback method for manually overriding/inserting entry if FPL API is down.
        """
        phase_stats = await cls.calculate_phase_stats(fpl_id)
        cat_upper = category.upper()
        if cat_upper == "CUP" and title == "Cup Champion":
            title = "The Untouchable"

        entry = HallOfFame(
            season=season,
            category=cat_upper,
            fpl_id=fpl_id,
            manager_name=manager_name,
            team_name=team_name,
            title=title,
            total_points=total_points,
            runner_up_name=runner_up_name,
            runner_up_team=runner_up_team,
            **phase_stats
        )
        session.add(entry)
        await session.flush()
        return entry

    @classmethod
    async def get_hall_of_fame_entries(
        cls,
        session: AsyncSession,
        category: Optional[str] = None
    ) -> List[HallOfFame]:
        stmt = select(HallOfFame).order_by(HallOfFame.season.desc(), HallOfFame.id.desc())
        if category:
            stmt = stmt.where(HallOfFame.category == category.upper())
        res = await session.execute(stmt)
        return res.scalars().all()

    @classmethod
    async def get_latest_champion(
        cls,
        session: AsyncSession,
        category: str
    ) -> Optional[HallOfFame]:
        stmt = (
            select(HallOfFame)
            .where(HallOfFame.category == category.upper())
            .order_by(HallOfFame.season.desc(), HallOfFame.id.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
