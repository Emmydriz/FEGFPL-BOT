import datetime
from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, ForeignKey, Boolean, Text, Float
)
from sqlalchemy.orm import relationship
from database.db import Base


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    feg_member_id = Column(String(50), unique=True, index=True, nullable=False)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    telegram_username = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=False)
    registration_status = Column(String(50), default="UNREGISTERED", index=True)
    account_status = Column(String(50), default="ACTIVE")
    referral_code = Column(String(50), unique=True, index=True, nullable=False)
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Season & Renewal Management
    current_season = Column(String(50), default="2026/2027")
    membership_status = Column(String(50), default="ACTIVE", index=True)  # ACTIVE, PENDING_RENEWAL, EXPIRED
    renewal_deadline = Column(DateTime, nullable=True)
    renewal_payment_status = Column(String(50), default="NOT_SUBMITTED", index=True)  # NOT_SUBMITTED, PENDING_APPROVAL, APPROVED

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    fpl_profile = relationship("FPLProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    payout_account = relationship("PayoutAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    community_invites = relationship("CommunityInvite", back_populates="user", cascade="all, delete-orphan")
    rewards = relationship("Reward", back_populates="user", cascade="all, delete-orphan")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    role = Column(String(50), nullable=False)  # SUPER_ADMIN, FINANCE_ADMIN, CONTENT_ADMIN
    permissions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class FPLProfile(Base):
    __tablename__ = "fpl_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    fpl_id = Column(BigInteger, index=True, nullable=False)
    manager_name = Column(String(200), nullable=True)
    team_name = Column(String(200), nullable=True)
    classic_status = Column(String(50), default="PENDING")
    h2h_status = Column(String(50), default="PENDING")
    cup_status = Column(String(50), default="NOT_ACTIVE")
    last_fpl_sync = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="fpl_profile")


class PayoutAccount(Base):
    __tablename__ = "payout_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    bank_name = Column(String(100), nullable=False)
    account_name = Column(String(200), nullable=False)
    encrypted_account_number = Column(Text, nullable=False)
    masked_account_number = Column(String(20), nullable=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="payout_account")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, default=5000.0, nullable=False)
    payment_method = Column(String(50), default="BANK_TRANSFER")
    proof_file_id = Column(String(500), nullable=True)
    payment_reference = Column(String(100), nullable=True)
    payment_status = Column(String(50), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED
    payment_account_version = Column(Integer, default=1)
    reviewed_by_admin_id = Column(BigInteger, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="payments")


class PaymentAccountConfig(Base):
    __tablename__ = "payment_account_configs"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(Integer, nullable=False, index=True)
    bank_name = Column(String(100), nullable=False)
    account_name = Column(String(200), nullable=False)
    account_number = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    effective_from = Column(DateTime, default=utcnow)
    effective_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    target = Column(String(200), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class CommunityInvite(Base):
    __tablename__ = "community_invites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    invite_link = Column(String(500), nullable=False)
    invite_link_id = Column(String(100), nullable=True)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, USED, REVOKED
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="community_invites")


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referrer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    referred_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    status = Column(String(50), default="PENDING")  # PENDING, APPROVED, FAILED
    created_at = Column(DateTime, default=utcnow)
    approved_at = Column(DateTime, nullable=True)


class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reward_type = Column(String(50), nullable=False)  # REFERRAL_MILESTONE, MANAGER_OF_WEEK, CUP_REWARD
    competition = Column(String(50), default="FEG_FPL")
    gameweek = Column(Integer, nullable=True)
    amount = Column(Float, nullable=False)
    highest_milestone_count = Column(Integer, nullable=True)
    status = Column(String(50), default="PENDING_APPROVAL")  # PENDING_APPROVAL, APPROVED, PAID, REJECTED, HOLD
    approved_by_admin_id = Column(BigInteger, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    payment_reference = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="rewards")


class HallOfFame(Base):
    __tablename__ = "hall_of_fame"

    id = Column(Integer, primary_key=True, index=True)
    season = Column(String(20), nullable=False, index=True)  # e.g., "2026/27"
    category = Column(String(20), nullable=False, index=True)  # CLASSIC, H2H, CUP
    fpl_id = Column(BigInteger, nullable=False)
    manager_name = Column(String(200), nullable=False)
    team_name = Column(String(200), nullable=False)
    title = Column(String(100), nullable=False)  # e.g., "Classic Champion", "The Untouchable"
    total_points = Column(Integer, nullable=False, default=0)
    runner_up_name = Column(String(200), nullable=True)
    runner_up_team = Column(String(200), nullable=True)

    # Phase Breakdown
    early_phase_pts = Column(Integer, default=0)  # GW1–12
    early_standout_gw = Column(String(100), nullable=True)  # e.g., "GW8 (89 PTS)"
    mid_phase_pts = Column(Integer, default=0)  # GW13–26
    mid_standout_gw = Column(String(100), nullable=True)  # e.g., "GW18 (96 PTS)"
    late_phase_pts = Column(Integer, default=0)  # GW27–38
    late_standout_gw = Column(String(100), nullable=True)  # e.g., "GW34 (112 PTS)"

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class HallOfFameRecord(Base):
    __tablename__ = "hall_of_fame_records"

    id = Column(Integer, primary_key=True, index=True)
    feg_member_id = Column(String(50), nullable=False, index=True)
    season = Column(String(20), nullable=False, index=True)  # e.g., "2026/2027"
    category = Column(String(20), nullable=False, index=True)  # CLASSIC, H2H, CUP
    rank = Column(Integer, default=1)  # 1 = Champion, 2 = Runner Up, 3 = Third Place
    manager_name = Column(String(200), nullable=False)
    team_name = Column(String(200), nullable=False)
    title = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)
