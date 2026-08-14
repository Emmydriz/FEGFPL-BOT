import pytest
from sqlalchemy import select
from database.db import init_db, get_db_session
from database.models import User, AuditLog, PaymentAccountConfig
from database.crypto import encrypt_string, decrypt_string, mask_account_number
from database.repository import create_user, add_audit_log, create_payment_account_config


@pytest.mark.asyncio
async def test_database_initialization_and_user_creation():
    await init_db()

    async with get_db_session() as session:
        user = await create_user(
            session=session,
            telegram_id=987654321,
            full_name="Emmanuel Ilesanmi",
            telegram_username="eilesanmi"
        )
        assert user.id is not None
        assert user.feg_member_id.startswith("FEG-2026-")
        assert user.referral_code.startswith("FEG-REF-")
        assert user.registration_status == "REGISTERING"


@pytest.mark.asyncio
async def test_encryption_and_masking():
    account_num = "0123456789"
    encrypted = encrypt_string(account_num)
    assert encrypted != account_num

    decrypted = decrypt_string(encrypted)
    assert decrypted == account_num

    masked = mask_account_number(account_num)
    assert masked == "••••6789"


@pytest.mark.asyncio
async def test_audit_log_recording():
    await init_db()

    async with get_db_session() as session:
        log = await add_audit_log(
            session=session,
            admin_id=123456789,
            role="SUPER_ADMIN",
            action="TEST_ACTION",
            target="SYSTEM",
            details="Database test audit log"
        )
        assert log.id is not None
        assert log.action == "TEST_ACTION"
        assert log.admin_id == 123456789


@pytest.mark.asyncio
async def test_payment_account_config_versioning():
    await init_db()

    async with get_db_session() as session:
        cfg1 = await create_payment_account_config(
            session=session,
            bank_name="Bank A",
            account_name="FEG FPL 1",
            account_number="1111111111"
        )
        assert cfg1.is_active is True
        v1 = cfg1.version

        cfg2 = await create_payment_account_config(
            session=session,
            bank_name="Bank B",
            account_name="FEG FPL 2",
            account_number="2222222222"
        )
        assert cfg2.version == v1 + 1
        assert cfg2.is_active is True

        # Re-fetch cfg1 to verify deactivation
        stmt = select(PaymentAccountConfig).where(PaymentAccountConfig.id == cfg1.id)
        res = await session.execute(stmt)
        refreshed_cfg1 = res.scalar_one()
        assert refreshed_cfg1.is_active is False
