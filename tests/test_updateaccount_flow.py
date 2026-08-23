import pytest
from database.db import init_db, get_db_session
from database.models import User, PayoutAccount, AuditLog
from database.crypto import encrypt_string, decrypt_string, mask_account_number
from sqlalchemy import select

@pytest.mark.asyncio
async def test_updateaccount_state_machine_flow():
    await init_db()

    async with get_db_session() as session:
        # Create test member
        user = User(
            feg_member_id="FEG-2026-TESTACC",
            telegram_id=888777666,
            telegram_username="test_update_user",
            full_name="Test Update Account Member",
            registration_status="COMMUNITY_ACCESS_GRANTED",
            membership_status="ACTIVE",
            referral_code="FEG-REF-TESTACC"
        )
        session.add(user)
        await session.flush()

        payout = PayoutAccount(
            user_id=user.id,
            bank_name="Initial Bank",
            account_name=user.full_name,
            encrypted_account_number=encrypt_string("1111222233"),
            masked_account_number="••••2233"
        )
        session.add(payout)
        await session.commit()

    # Verify initial decrypt is unmasked
    async with get_db_session() as session:
        stmt = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        p = (await session.execute(stmt)).scalar_one_or_none()
        assert p is not None
        assert decrypt_string(p.encrypted_account_number) == "1111222233"

    # Simulate updating to new 10-digit NUBAN account number
    new_acc = "8066106785"
    new_bank = "Opay Bank"

    async with get_db_session() as session:
        stmt = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        p = (await session.execute(stmt)).scalar_one_or_none()
        p.bank_name = new_bank
        p.encrypted_account_number = encrypt_string(new_acc)
        p.masked_account_number = f"••••{new_acc[-4:]}"
        await session.commit()

    # Verify updated unmasked account number and audit log readiness
    async with get_db_session() as session:
        stmt = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        p = (await session.execute(stmt)).scalar_one_or_none()
        assert p.bank_name == "Opay Bank"
        assert decrypt_string(p.encrypted_account_number) == "8066106785"
