import datetime
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Payment, PaymentAccountConfig
from database.repository import (
    get_latest_active_payment_account,
    create_payment_account_config,
    add_audit_log
)


class PaymentService:
    @staticmethod
    async def submit_payment_proof(
        session: AsyncSession,
        user: User,
        proof_file_id: str,
        amount: float = 5000.0,
        payment_reference: Optional[str] = None
    ) -> Payment:
        active_config = await get_latest_active_payment_account(session)
        if not active_config:
            # Seed initial active config if none exists
            from config.settings import settings
            active_config = await create_payment_account_config(
                session=session,
                bank_name=settings.FEG_PAYMENT_BANK,
                account_name=settings.FEG_PAYMENT_ACCOUNT_NAME,
                account_number=settings.FEG_PAYMENT_ACCOUNT_NUMBER
            )

        payment = Payment(
            user_id=user.id,
            amount=amount,
            payment_method="BANK_TRANSFER",
            proof_file_id=proof_file_id,
            payment_reference=payment_reference,
            payment_status="PENDING",
            payment_account_version=active_config.version
        )
        session.add(payment)
        user.registration_status = "PAYMENT_PENDING"
        await session.flush()
        return payment

    @staticmethod
    async def approve_payment(
        session: AsyncSession,
        payment_id: int,
        admin_id: int,
        admin_role: str
    ) -> Tuple[bool, Optional[Payment], Optional[User]]:
        stmt = select(Payment).where(Payment.id == payment_id)
        res = await session.execute(stmt)
        payment = res.scalar_one_or_none()

        if not payment:
            return False, None, None

        payment.payment_status = "APPROVED"
        payment.reviewed_by_admin_id = admin_id
        payment.reviewed_at = datetime.datetime.now(datetime.timezone.utc)

        stmt_user = select(User).where(User.id == payment.user_id)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if user:
            user.registration_status = "APPROVED"

            # Approve Referral status & evaluate milestone rewards for referrer
            from database.models import Referral
            from services.referral_service import ReferralService

            stmt_ref = select(Referral).where(Referral.referred_user_id == user.id)
            res_ref = await session.execute(stmt_ref)
            ref_entry = res_ref.scalar_one_or_none()

            if ref_entry:
                ref_entry.status = "APPROVED"
                if ref_entry.referrer_user_id:
                    await ReferralService.evaluate_referrals_and_rewards(session, ref_entry.referrer_user_id)
            elif user.referred_by_id:
                stmt_r = select(Referral).where(
                    Referral.referrer_user_id == user.referred_by_id,
                    Referral.referred_user_id == user.id
                )
                res_r = await session.execute(stmt_r)
                r_record = res_r.scalar_one_or_none()
                if not r_record:
                    r_record = Referral(
                        referrer_user_id=user.referred_by_id,
                        referred_user_id=user.id,
                        status="APPROVED"
                    )
                    session.add(r_record)
                else:
                    r_record.status = "APPROVED"
                await ReferralService.evaluate_referrals_and_rewards(session, user.referred_by_id)

        await add_audit_log(
            session=session,
            admin_id=admin_id,
            role=admin_role,
            action="APPROVED_PAYMENT",
            target=f"User ID {payment.user_id}",
            details=f"Approved Payment ID {payment.id} for amount ₦{payment.amount}"
        )

        await session.flush()
        return True, payment, user

    @staticmethod
    async def reject_payment(
        session: AsyncSession,
        payment_id: int,
        admin_id: int,
        admin_role: str,
        reason: str = "Invalid proof of payment"
    ) -> Tuple[bool, Optional[Payment], Optional[User]]:
        stmt = select(Payment).where(Payment.id == payment_id)
        res = await session.execute(stmt)
        payment = res.scalar_one_or_none()

        if not payment:
            return False, None, None

        payment.payment_status = "REJECTED"
        payment.rejection_reason = reason
        payment.reviewed_by_admin_id = admin_id
        payment.reviewed_at = datetime.datetime.now(datetime.timezone.utc)

        stmt_user = select(User).where(User.id == payment.user_id)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if user:
            user.registration_status = "PAYMENT_REJECTED"

        await add_audit_log(
            session=session,
            admin_id=admin_id,
            role=admin_role,
            action="REJECTED_PAYMENT",
            target=f"User ID {payment.user_id}",
            details=f"Rejected Payment ID {payment.id}. Reason: {reason}"
        )

        await session.flush()
        return True, payment, user
