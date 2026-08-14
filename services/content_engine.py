from typing import Dict, Any, List


class ContentEngine:
    @staticmethod
    def generate_captain_picks(gameweek: int) -> str:
        return (
            f"🎯 **CAPTAIN PICKS — GAMEWEEK {gameweek}** ⚽\n\n"
            "🥇 **Mohamed Salah** (LIV vs MUN) — Form: 8.5 | Fixture Rating: 4/5\n"
            "🥈 **Erling Haaland** (MCI vs EVE) — Form: 9.0 | Fixture Rating: 5/5\n"
            "🥉 **Bukayo Saka** (ARS vs WOL) — Form: 7.8 | Fixture Rating: 4/5\n\n"
            "💎 **Differential Captain Option:**\n"
            "**Cole Palmer** (CHE vs CRY) — Ownership: 14.2%\n\n"
            "⚠️ *Note: FEG content recommendations are analytical previews, not guaranteed outcomes.*"
        )

    @staticmethod
    def generate_differentials(gameweek: int) -> str:
        return (
            f"💎 **DIFFERENTIAL PICKS — GAMEWEEK {gameweek}**\n\n"
            "1. **Bryan Mbeumo** (BRE) — Ownership: 7.4% | Fixture: WHU (H)\n"
            "2. **Dominic Solanke** (TOT) — Ownership: 8.1% | Fixture: IPS (H)\n"
            "3. **Antoine Semenyo** (BOU) — Ownership: 4.8% | Fixture: SOU (A)\n\n"
            "Targeting differentials with under 10% ownership can boost your FEG Classic & H2H rank!"
        )

    @staticmethod
    def generate_price_change_watch() -> str:
        return (
            "💰 **PRICE CHANGE WATCH**\n\n"
            "📈 **RISERS (Expected Price Increase):**\n"
            "• Haaland (MCI) £15.2m ➡️ £15.3m\n"
            "• Palmer (CHE) £10.8m ➡️ £10.9m\n\n"
            "📉 **FALLERS (Expected Price Decrease):**\n"
            "• Foden (MCI) £9.2m ➡️ £9.1m\n"
            "• Watkins (AVL) £8.9m ➡️ £8.8m"
        )

    @staticmethod
    def generate_gameweek_preview(gameweek: int) -> str:
        return (
            f"📋 **FEG FPL — GAMEWEEK {gameweek} PREVIEW**\n\n"
            f"⏰ **Deadline:** Friday 18:30 GMT\n\n"
            "🔥 **Key Fixtures:**\n"
            "• Arsenal vs Chelsea\n"
            "• Man City vs Liverpool\n\n"
            "💡 **Transfer Strategy:**\n"
            "Focus on teams with fixture swings over the next 4 gameweeks.\n"
            "Make sure your FEG Classic & H2H squads are updated before the deadline!"
        )
