import pytest
from database.db import get_db_session
from services.member_service import MemberService
from services.fpl_service import FPLService
from services.payment_service import PaymentService
from database.crypto import decrypt_string


@pytest.mark.asyncio
async def test_member_registration_and_fpl_profile():
    async with get_db_session() as session:
        user = await MemberService.get_or_start_registration(
            session=session,
            telegram_id=11223344,
            full_name="Emmanuel Ilesanmi",
            telegram_username="eilesanmi"
        )
        assert user.full_name == "Emmanuel Ilesanmi"
        assert user.feg_member_id.startswith("FEG-2026-")

        profile = await MemberService.update_fpl_profile(
            session=session,
            user=user,
            fpl_id=12345678,
            manager_name="Emmanuel Ilesanmi",
            team_name="FEG Champions"
        )
        assert profile.fpl_id == 12345678
        assert profile.manager_name == "Emmanuel Ilesanmi"

        payout = await MemberService.save_payout_account(
            session=session,
            user=user,
            bank_name="Access Bank",
            account_name="Emmanuel Ilesanmi",
            account_number="0123456789"
        )
        assert payout.masked_account_number == "••••6789"
        assert decrypt_string(payout.encrypted_account_number) == "0123456789"


@pytest.mark.asyncio
async def test_duplicate_fpl_id_prevention():
    async with get_db_session() as session:
        user1 = await MemberService.get_or_start_registration(
            session=session, telegram_id=10000001, full_name="User One"
        )
        await MemberService.update_fpl_profile(session, user1, 88888888, "User One", "Team One")

        user2 = await MemberService.get_or_start_registration(
            session=session, telegram_id=10000002, full_name="User Two"
        )
        duplicate = await MemberService.check_duplicate_fpl_id(session, 88888888, user2.id)

        assert duplicate is not None
        assert duplicate.id == user1.id


@pytest.mark.asyncio
async def test_payment_submission():
    async with get_db_session() as session:
        user = await MemberService.get_or_start_registration(
            session=session, telegram_id=55667788, full_name="Test Payer"
        )
        payment = await PaymentService.submit_payment_proof(
            session=session,
            user=user,
            proof_file_id="mock_file_id_12345",
            amount=5000.0
        )
        assert payment.payment_status == "PENDING"
        assert user.registration_status == "PAYMENT_PENDING"
        assert payment.proof_file_id == "mock_file_id_12345"
