import pytest
from sqlalchemy import select
from database.db import get_db_session
from database.models import AuditLog, CommunityInvite
from services.member_service import MemberService
from services.payment_service import PaymentService
from services.community_service import CommunityService


@pytest.mark.asyncio
async def test_admin_payment_approval_and_community_invite():
    async with get_db_session() as session:
        user = await MemberService.get_or_start_registration(
            session=session, telegram_id=99887766, full_name="Payment Winner"
        )
        payment = await PaymentService.submit_payment_proof(
            session=session,
            user=user,
            proof_file_id="proof_photo_123"
        )

        success, approved_pay, approved_user = await PaymentService.approve_payment(
            session=session,
            payment_id=payment.id,
            admin_id=123456789,
            admin_role="SUPER_ADMIN"
        )
        assert success is True
        assert approved_pay.payment_status == "APPROVED"
        assert approved_user.registration_status == "APPROVED"

        invite = await CommunityService.create_one_time_invite(session, approved_user)
        assert invite.status == "ACTIVE"
        assert approved_user.registration_status == "COMMUNITY_ACCESS_GRANTED"
        assert invite.invite_link is not None

        # Check Audit Log
        stmt = select(AuditLog).where(AuditLog.action == "APPROVED_PAYMENT")
        res = await session.execute(stmt)
        audit = res.scalar_one_or_none()
        assert audit is not None
        assert audit.admin_id == 123456789


@pytest.mark.asyncio
async def test_admin_payment_rejection():
    async with get_db_session() as session:
        user = await MemberService.get_or_start_registration(
            session=session, telegram_id=33445566, full_name="Fake Payer"
        )
        payment = await PaymentService.submit_payment_proof(
            session=session,
            user=user,
            proof_file_id="fake_photo_999"
        )

        success, rejected_pay, rejected_user = await PaymentService.reject_payment(
            session=session,
            payment_id=payment.id,
            admin_id=234567890,
            admin_role="FINANCE_ADMIN",
            reason="Unconfirmed bank deposit"
        )
        assert success is True
        assert rejected_pay.payment_status == "REJECTED"
        assert rejected_user.registration_status == "PAYMENT_REJECTED"
        assert rejected_pay.rejection_reason == "Unconfirmed bank deposit"

        stmt = select(AuditLog).where(AuditLog.action == "REJECTED_PAYMENT")
        res = await session.execute(stmt)
        audit = res.scalar_one_or_none()
        assert audit is not None
        assert audit.admin_id == 234567890
