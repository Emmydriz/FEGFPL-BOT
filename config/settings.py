import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    BOT_TOKEN: str = "123456789:ABCdefGHIjklMNOpqrsTUVwxyZ"
    DATABASE_URL: str = "sqlite+aiosqlite:///./feg_fpl.db"

    FEG_BOT_USERNAME: str = "@FEGFPL_Bot"
    FEG_COMMUNITY_CHAT_ID: int = -100123456789
    FEG_ANNOUNCEMENT_CHANNEL_ID: int = -100987654321
    FEG_COMMUNITY_INVITE_LINK: str = "https://t.me/+feg_invite_link"

    # Payment details
    FEG_REGISTRATION_FEE: int = 5000
    FEG_PAYMENT_METHOD: str = "BANK_TRANSFER"
    FEG_PAYMENT_BANK: str = "Access Bank"
    FEG_PAYMENT_ACCOUNT_NAME: str = "FEG FPL"
    FEG_PAYMENT_ACCOUNT_NUMBER: str = "0123456789"

    # Numeric Telegram Admin IDs
    ADMIN_SUPER_ID: int = 123456789
    ADMIN_FINANCE_ID: int = 234567890
    ADMIN_CONTENT_ID: int = 345678901

    # Competition settings
    FPL_CLASSIC_LEAGUE_ID: int = 123456
    FPL_CLASSIC_INVITE_CODE: str = "ABC123"
    FPL_CLASSIC_INVITE_LINK: str = "https://fantasy.premierleague.com/leagues/auto-join/ABC123"

    FPL_H2H_LEAGUE_ID: int = 789012
    FPL_H2H_INVITE_CODE: str = "XYZ789"
    FPL_H2H_INVITE_LINK: str = "https://fantasy.premierleague.com/leagues/auto-join/XYZ789"

    FEG_START_GAMEWEEK: int = 4
    FEG_REGISTRATION_DEADLINE: Optional[str] = "2026-08-30T23:59:59"
    FEG_CUP_START_GAMEWEEK: int = 19

    # Rewards
    REFERRAL_MILESTONE_1: int = 3
    REFERRAL_REWARD_1: int = 2000
    REFERRAL_MILESTONE_2: int = 5
    REFERRAL_REWARD_2: int = 4000
    REFERRAL_MILESTONE_3: int = 7
    REFERRAL_REWARD_3: int = 6000
    REFERRAL_MILESTONE_4: int = 10
    REFERRAL_REWARD_4: int = 10000
    MANAGER_OF_WEEK_REWARD: int = 1000
    FEG_PRIZE_POOL_PUBLIC_TEXT: str = "₦150,000+"

    CONTENT_AUTO_PUBLISH: bool = False
    LIVE_UPDATE_INTERVAL: int = 60
    SECRET_KEY: str = "supersecretkey_change_me_in_production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
