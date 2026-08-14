import datetime
from typing import Optional, List
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    User, Admin, FPLProfile, PayoutAccount, Payment,
    PaymentAccountConfig, AuditLog, SystemSetting, CommunityInvite
)
from database.crypto import encrypt_string, mask_account_number


async def generate_feg_member_id(session: AsyncSession) -> str:
    stmt = select(func.count(User.id))
    result = await session.execute(stmt)
    count = result.scalar() or 0
    next_num = count + 1
    return f"FEG-2026-{next_num:06d}"


async def generate_referral_code(session: AsyncSession) -> str:
    stmt = select(func.count(User.id))
    result = await session.execute(stmt)
    count = result.scalar() or 0
    next_num = count + 1
    return f"FEG-REF-{next_num:06d}"


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_feg_id(session: AsyncSession, feg_member_id: str) -> Optional[User]:
    stmt = select(User).where(User.feg_member_id == feg_member_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_fpl_id(session: AsyncSession, fpl_id: int) -> Optional[User]:
    stmt = select(User).join(FPLProfile).where(FPLProfile.fpl_id == fpl_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    telegram_username: Optional[str] = None,
    referred_by_id: Optional[int] = None
) -> User:
    member_id = await generate_feg_member_id(session)
    ref_code = await generate_referral_code(session)

    user = User(
        feg_member_id=member_id,
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        full_name=full_name,
        registration_status="REGISTERING",
        referral_code=ref_code,
        referred_by_id=referred_by_id
    )
    session.add(user)
    await session.flush()
    return user


async def add_audit_log(
    session: AsyncSession,
    admin_id: int,
    role: str,
    action: str,
    target: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    log_entry = AuditLog(
        admin_id=admin_id,
        role=role,
        action=action,
        target=target,
        details=details,
        ip_address=ip_address,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    session.add(log_entry)
    await session.flush()
    return log_entry


async def get_latest_active_payment_account(session: AsyncSession) -> Optional[PaymentAccountConfig]:
    stmt = select(PaymentAccountConfig).where(PaymentAccountConfig.is_active == True).order_by(PaymentAccountConfig.version.desc())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_payment_account_config(
    session: AsyncSession,
    bank_name: str,
    account_name: str,
    account_number: str
) -> PaymentAccountConfig:
    # Deactivate previous active configs
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    await session.execute(
        update(PaymentAccountConfig)
        .where(PaymentAccountConfig.is_active == True)
        .values(is_active=False, effective_to=now_utc)
    )

    # Get max version
    stmt = select(func.max(PaymentAccountConfig.version))
    result = await session.execute(stmt)
    max_ver = result.scalar() or 0

    new_config = PaymentAccountConfig(
        version=max_ver + 1,
        bank_name=bank_name,
        account_name=account_name,
        account_number=account_number,
        is_active=True,
        effective_from=now_utc
    )
    session.add(new_config)
    await session.flush()
    return new_config


async def sync_payment_account_from_settings(session: AsyncSession) -> PaymentAccountConfig:
    from config.settings import settings
    active = await get_latest_active_payment_account(session)

    if (
        not active or
        active.bank_name != settings.FEG_PAYMENT_BANK or
        active.account_name != settings.FEG_PAYMENT_ACCOUNT_NAME or
        active.account_number != settings.FEG_PAYMENT_ACCOUNT_NUMBER
    ):
        active = await create_payment_account_config(
            session=session,
            bank_name=settings.FEG_PAYMENT_BANK,
            account_name=settings.FEG_PAYMENT_ACCOUNT_NAME,
            account_number=settings.FEG_PAYMENT_ACCOUNT_NUMBER
        )
    return active
