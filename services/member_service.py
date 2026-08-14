from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, FPLProfile, PayoutAccount
from database.crypto import encrypt_string, mask_account_number
from database.repository import create_user, get_user_by_telegram_id as repo_get_user_by_telegram_id, get_user_by_fpl_id


class MemberService:
    @staticmethod
    async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        return await repo_get_user_by_telegram_id(session, telegram_id)

    @staticmethod
    async def get_or_start_registration(
        session: AsyncSession,
        telegram_id: int,
        full_name: str,
        telegram_username: Optional[str] = None
    ) -> User:
        user = await repo_get_user_by_telegram_id(session, telegram_id)
        if not user:
            user = await create_user(
                session=session,
                telegram_id=telegram_id,
                full_name=full_name,
                telegram_username=telegram_username
            )
        else:
            user.full_name = full_name
            user.telegram_username = telegram_username
            await session.flush()
        return user

    @staticmethod
    async def check_duplicate_fpl_id(session: AsyncSession, fpl_id: int, current_user_id: int) -> Optional[User]:
        existing_user = await get_user_by_fpl_id(session, fpl_id)
        if existing_user and existing_user.id != current_user_id:
            return existing_user
        return None

    @staticmethod
    async def update_fpl_profile(
        session: AsyncSession,
        user: User,
        fpl_id: int,
        manager_name: str,
        team_name: str
    ) -> FPLProfile:
        stmt = select(FPLProfile).where(FPLProfile.user_id == user.id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()

        if not profile:
            profile = FPLProfile(
                user_id=user.id,
                fpl_id=fpl_id,
                manager_name=manager_name,
                team_name=team_name,
                classic_status="PENDING",
                h2h_status="PENDING",
                cup_status="NOT_ACTIVE"
            )
            session.add(profile)
        else:
            profile.fpl_id = fpl_id
            profile.manager_name = manager_name
            profile.team_name = team_name

        await session.flush()
        return profile

    @staticmethod
    async def save_payout_account(
        session: AsyncSession,
        user: User,
        bank_name: str,
        account_name: str,
        account_number: str
    ) -> PayoutAccount:
        stmt = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
        res = await session.execute(stmt)
        payout = res.scalar_one_or_none()

        encrypted_acc = encrypt_string(account_number)
        masked_acc = mask_account_number(account_number)

        if not payout:
            payout = PayoutAccount(
                user_id=user.id,
                bank_name=bank_name,
                account_name=account_name,
                encrypted_account_number=encrypted_acc,
                masked_account_number=masked_acc
            )
            session.add(payout)
        else:
            payout.bank_name = bank_name
            payout.account_name = account_name
            payout.encrypted_account_number = encrypted_acc
            payout.masked_account_number = masked_acc

        await session.flush()
        return payout
