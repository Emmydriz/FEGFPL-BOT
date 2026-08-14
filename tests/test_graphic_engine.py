import os
from services.graphic_engine import GraphicEngine


def test_team_of_gw_graphic_generation():
    players = [
        {"name": "Raya", "position": "GK", "points": 8},
        {"name": "Gabriel", "position": "DEF", "points": 12},
        {"name": "Salah", "position": "MID", "points": 16, "is_captain": True},
        {"name": "Haaland", "position": "FWD", "points": 15}
    ]

    output_path = GraphicEngine.generate_team_of_gw_graphic(
        gameweek=4,
        formation="1-1-1-1",
        players=players,
        total_points=51
    )

    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 0
