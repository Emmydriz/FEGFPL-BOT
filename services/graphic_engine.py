import os
from PIL import Image, ImageDraw, ImageFont
from config.logging_config import logger


class GraphicEngine:
    OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "graphics")

    @classmethod
    def generate_team_of_gw_graphic(
        cls,
        gameweek: int,
        formation: str,
        players: list,
        total_points: int
    ) -> str:
        """
        Generates a clean Team of the Gameweek graphic image.
        """
        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)
        filename = f"team_of_gw_gw{gameweek}.png"
        output_path = os.path.join(cls.OUTPUT_DIR, filename)

        width, height = 800, 1000
        # Dark green/blue pitch theme
        bg_color = (15, 32, 39)
        pitch_color = (20, 70, 45)
        border_color = (255, 215, 0) # Gold accent

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Draw Header Banner
        draw.rectangle([(20, 20), (width - 20, 120)], fill=(10, 20, 30), outline=border_color, width=3)
        draw.text((250, 35), f"FEG FPL — GAMEWEEK {gameweek}", fill=(255, 215, 0))
        draw.text((290, 70), "TEAM OF THE GAMEWEEK", fill=(255, 255, 255))

        # Pitch Boundary
        draw.rectangle([(40, 150), (width - 40, height - 80)], fill=pitch_color, outline=(255, 255, 255), width=2)
        # Center Line
        draw.line([(40, 520), (width - 40, 520)], fill=(255, 255, 255), width=2)

        # Total Points Banner
        draw.rectangle([(40, height - 60), (width - 40, height - 20)], fill=(10, 20, 30), outline=border_color, width=2)
        draw.text((280, height - 50), f"TOTAL GW POINTS: {total_points} PTS", fill=(255, 215, 0))

        # Draw Player Boxes
        # Simple position grid layout
        y_offsets = {
            "GK": 220,
            "DEF": 380,
            "MID": 580,
            "FWD": 780
        }

        # Group players by position
        grouped = {"GK": [], "DEF": [], "MID": [], "FWD": []}
        for p in players:
            pos = p.get("position", "MID").upper()
            if pos in grouped:
                grouped[pos].append(p)
            else:
                grouped["MID"].append(p)

        for pos, pos_players in grouped.items():
            y = y_offsets.get(pos, 500)
            n = len(pos_players)
            if n == 0:
                continue
            spacing = (width - 80) // (n + 1)
            for idx, p in enumerate(pos_players):
                x = 40 + spacing * (idx + 1)
                p_name = p.get("name", "Player")
                pts = p.get("points", 0)
                is_cap = p.get("is_captain", False)

                # Card Box
                box_w, box_h = 110, 50
                left = x - box_w // 2
                top = y - box_h // 2
                draw.rectangle([(left, top), (left + box_w, top + box_h)], fill=(10, 25, 40), outline=border_color if is_cap else (200, 200, 200), width=2)

                card_text = f"{p_name}{' (C)' if is_cap else ''}\n{pts} pts"
                draw.text((left + 10, top + 10), card_text, fill=(255, 255, 255))

        img.save(output_path, "PNG")
        logger.info(f"Generated Team of GW graphic at {output_path}")
        return output_path
