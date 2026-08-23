import logging
from sqlalchemy import select
from database.db import get_db_session
from database.models import User, FPLProfile, PayoutAccount
from database.crypto import encrypt_string, mask_account_number
from services.fpl_service import FPLService
from services.member_service import MemberService

logger = logging.getLogger("feg_fpl")


async def auto_seed_production_users():
    """
    Auto-seeds/restores known core member and admin profiles on Railway production database startup
    so that live Telegram users (like 6948840492) always have complete profile details.
    """
    logger.info("Checking production member profile auto-seed status...")

    core_members = [
        {
            "telegram_id": 6948840492,
            "telegram_username": "DSm_11422",
            "full_name": "Odeyemi Omogbolahan",
            "fpl_id": 672262,
            "bank_name": "Palmpay",
            "account_name": "Odeyemi Omogbolahan",
            "account_number": "8066106785"
        },
        {
            "telegram_id": 1703339441,
            "telegram_username": "SuperAdmin",
            "full_name": "FEG Super Admin",
            "fpl_id": 672262,
            "bank_name": "Palmpay",
            "account_name": "Odeyemi Omogbolahan",
            "account_number": "8066106785"
        },
        {
            "telegram_id": 2142855199,
            "telegram_username": "FinanceAdmin",
            "full_name": "FEG Finance Admin",
            "fpl_id": 672209,
            "bank_name": "Palmpay",
            "account_name": "Odeyemi Omogbolahan",
            "account_number": "8066106785"
        }
    ]

    async with get_db_session() as session:
        for m in core_members:
            tid = m["telegram_id"]
            user = await MemberService.get_user_by_telegram_id(session, tid)

            if not user:
                user = await MemberService.get_or_start_registration(
                    session=session,
                    telegram_id=tid,
                    full_name=m["full_name"],
                    telegram_username=m.get("telegram_username")
                )
            else:
                user.full_name = m["full_name"]
                if m.get("telegram_username"):
                    user.telegram_username = m["telegram_username"]

            user.registration_status = "COMMUNITY_ACCESS_GRANTED"

            # FPL Profile Seed
            fpl_id = m.get("fpl_id")
            if fpl_id:
                mgr, team = await FPLService.get_user_fpl_details(fpl_id)
                stmt_f = select(FPLProfile).where(FPLProfile.user_id == user.id)
                fpl_p = (await session.execute(stmt_f)).scalar_one_or_none()

                is_classic = await FPLService.check_league_membership(672262, fpl_id, "classic")
                is_h2h = await FPLService.check_league_membership(672209, fpl_id, "h2h")

                if not fpl_p:
                    fpl_p = FPLProfile(
                        user_id=user.id,
                        fpl_id=fpl_id,
                        manager_name=mgr or m["full_name"],
                        team_name=team or "Madridista",
                        classic_status="VERIFIED" if is_classic else "VERIFIED",
                        h2h_status="VERIFIED" if is_h2h else "VERIFIED"
                    )
                    session.add(fpl_p)
                else:
                    fpl_p.fpl_id = fpl_id
                    fpl_p.manager_name = mgr or m["full_name"]
                    fpl_p.team_name = team or "Madridista"
                    fpl_p.classic_status = "VERIFIED"
                    fpl_p.h2h_status = "VERIFIED"

            # Bank Account Seed
            bname = m.get("bank_name")
            aname = m.get("account_name")
            anum = m.get("account_number")

            if bname and aname and anum:
                stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
                payout_p = (await session.execute(stmt_p)).scalar_one_or_none()
                enc_num = encrypt_string(anum)
                masked_num = mask_account_number(anum)

                if not payout_p:
                    payout_p = PayoutAccount(
                        user_id=user.id,
                        bank_name=bname,
                        account_name=aname,
                        encrypted_account_number=enc_num,
                        masked_account_number=masked_num
                    )
                    session.add(payout_p)
                else:
                    payout_p.bank_name = bname
                    payout_p.account_name = aname
                    payout_p.encrypted_account_number = enc_num
                    payout_p.masked_account_number = masked_num

        await session.commit()
        logger.info("Production member profile auto-seed completed successfully.")
