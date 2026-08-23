import logging
from sqlalchemy import select
from database.db import get_db_session
from database.models import User, FPLProfile, PayoutAccount, Payment
from database.crypto import encrypt_string, mask_account_number
from services.member_service import MemberService
from services.backup_service import BackupService

logger = logging.getLogger("feg_fpl")

RESTORED_MEMBERS = [
    {
        "feg_member_id": "FEG-2026-000001",
        "full_name": "Ilesanmi Emmanuel Eniola",
        "telegram_id": 6948840492,
        "telegram_username": "DSm11422",
        "fpl_id": 3252334,
        "manager_name": "Emmanuel Ilesanmi",
        "team_name": "Emmydriz FC",
        "bank_name": "Opay",
        "account_name": "Ilesanmi Emmanuel Eniola",
        "account_number": "••••2502",
        "ref_code": "FEG-REF-000001"
    },
    {
        "feg_member_id": "FEG-2026-000002",
        "full_name": "Odeyemi Omogbolahan David",
        "telegram_id": 2112337065,
        "telegram_username": "yungdayv",
        "fpl_id": 3963471,
        "manager_name": "Yung Dave",
        "team_name": "Yung's Team",
        "bank_name": "Opay",
        "account_name": "Omogbolahan David Odeyemi",
        "account_number": "••••4486",
        "ref_code": "FEG-REF-000002"
    },
    {
        "feg_member_id": "FEG-2026-000003",
        "full_name": "Odeyemi Ojo juwon",
        "telegram_id": 7413474541,
        "telegram_username": "sarahrosey",
        "fpl_id": 4315480,
        "manager_name": "Ojo Juwon Odeyemi",
        "team_name": "Ojo Juwon's Team",
        "bank_name": "OPay",
        "account_name": "Ojo juwon odeyemi",
        "account_number": "••••3599",
        "ref_code": "FEG-REF-000003"
    },
    {
        "feg_member_id": "FEG-2026-000004",
        "full_name": "Ayodeji",
        "telegram_id": 6578792911,
        "telegram_username": "Deujot",
        "fpl_id": 2654430,
        "manager_name": "Ayodeji Ayodele",
        "team_name": "deujot",
        "bank_name": "Opay",
        "account_name": "Ayodeji Samuel Ayodele",
        "account_number": "••••9346",
        "ref_code": "FEG-REF-000004"
    },
    {
        "feg_member_id": "FEG-2026-000005",
        "full_name": "Folorunsho",
        "telegram_id": 8843081999,
        "telegram_username": None,
        "fpl_id": 2125777,
        "manager_name": "fholey fc",
        "team_name": "fholey fc",
        "bank_name": "Opay",
        "account_name": "Folorunsho salau",
        "account_number": "••••6343",
        "ref_code": "FEG-REF-000005"
    },
    {
        "feg_member_id": "FEG-2026-000006",
        "full_name": "Obahor Israel Uyoyo",
        "telegram_id": 8177243826,
        "telegram_username": None,
        "fpl_id": 3194693,
        "manager_name": "Obahor Israel",
        "team_name": "EazyGoing",
        "bank_name": "Moniepoint",
        "account_name": "Israel Uyoyo Obahor",
        "account_number": "••••4082",
        "ref_code": "FEG-REF-000006"
    },
    {
        "feg_member_id": "FEG-2026-000007",
        "full_name": "Victor Aladetoyinbo",
        "telegram_id": 5612222820,
        "telegram_username": "Vicreus11",
        "fpl_id": 6685299,
        "manager_name": "Victor Aladetoyinbo",
        "team_name": "VOIDSTEELO",
        "bank_name": "Access",
        "account_name": "Juwon Aladetoyinbo",
        "account_number": "••••8712",
        "ref_code": "FEG-REF-000007"
    },
    {
        "feg_member_id": "FEG-2026-000008",
        "full_name": "Juwon Aladetoyinbo",
        "telegram_id": 2076100149,
        "telegram_username": None,
        "fpl_id": 6269875,
        "manager_name": "Juwon Aladetoyinbo",
        "team_name": "HayJayFC",
        "bank_name": "Access Bank",
        "account_name": "Juwon Aladetoyinbo",
        "account_number": "••••8712",
        "ref_code": "FEG-REF-000008"
    },
    {
        "feg_member_id": "FEG-2026-000009",
        "full_name": "Adepoju Ridwan",
        "telegram_id": 564869988,
        "telegram_username": "whattttx",
        "fpl_id": 2370400,
        "manager_name": "Ridwan Adepoju",
        "team_name": "klausiv",
        "bank_name": "Opay",
        "account_name": "Adepoju Ridwan",
        "account_number": "••••7735",
        "ref_code": "FEG-REF-000009"
    },
    {
        "feg_member_id": "FEG-2026-000010",
        "full_name": "Nanicom",
        "telegram_id": 1808657798,
        "telegram_username": "Nanicom1",
        "fpl_id": 190863,
        "manager_name": "No peace For the wicked -",
        "team_name": "NanicomRonaldo",
        "bank_name": "Opay",
        "account_name": "Olalekan Olatunbosun",
        "account_number": "••••7496",
        "ref_code": "FEG-REF-000010"
    },
    {
        "feg_member_id": "FEG-2026-000011",
        "full_name": "Ayoade Ayomide David",
        "telegram_id": 6102771339,
        "telegram_username": "dave1940",
        "fpl_id": 8353657,
        "manager_name": "Ayomide Ayoade",
        "team_name": "big dave",
        "bank_name": "Palm pay",
        "account_name": "Ayoade Ayomide David",
        "account_number": "••••4981",
        "ref_code": "FEG-REF-000011"
    }
]


async def auto_seed_production_users():
    """
    Auto-seeds/restores all 11 approved member profiles on Railway production database startup.
    """
    logger.info("Auto-seeding 11 approved member profiles on startup...")

    # 1. Restore JSON backup first if available so custom admin updates are preserved
    await BackupService.restore_members_from_json_if_needed()

    async with get_db_session() as session:
        for data in RESTORED_MEMBERS:
            tid = data["telegram_id"]
            mid = data["feg_member_id"]

            stmt_t = select(User).where(User.telegram_id == tid)
            user = (await session.execute(stmt_t)).scalars().first()

            if not user:
                stmt_m = select(User).where(User.feg_member_id == mid)
                user = (await session.execute(stmt_m)).scalars().first()

            if not user:
                user = User(
                    feg_member_id=mid,
                    telegram_id=tid,
                    telegram_username=data["telegram_username"],
                    full_name=data["full_name"],
                    registration_status="COMMUNITY_ACCESS_GRANTED",
                    account_status="ACTIVE",
                    referral_code=data["ref_code"]
                )
                session.add(user)
                await session.flush()
            else:
                user.feg_member_id = mid
                user.telegram_id = tid
                if data["telegram_username"]:
                    user.telegram_username = data["telegram_username"]
                user.full_name = data["full_name"]
                user.registration_status = "COMMUNITY_ACCESS_GRANTED"

            # FPL Profile
            stmt_f = select(FPLProfile).where(FPLProfile.user_id == user.id)
            fpl_p = (await session.execute(stmt_f)).scalar_one_or_none()

            if not fpl_p:
                fpl_p = FPLProfile(
                    user_id=user.id,
                    fpl_id=data["fpl_id"],
                    manager_name=data["manager_name"],
                    team_name=data["team_name"],
                    classic_status="VERIFIED",
                    h2h_status="VERIFIED",
                    cup_status="NOT_ACTIVE"
                )
                session.add(fpl_p)

            # Payout Account - ONLY create if not existing, NEVER overwrite updated bank numbers
            stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
            payout_p = (await session.execute(stmt_p)).scalar_one_or_none()

            if not payout_p:
                raw_acc_num = data["account_number"]
                enc_acc_num = encrypt_string(raw_acc_num)
                masked_acc_num = mask_account_number(raw_acc_num)

                payout_p = PayoutAccount(
                    user_id=user.id,
                    bank_name=data["bank_name"],
                    account_name=data["account_name"],
                    encrypted_account_number=enc_acc_num,
                    masked_account_number=masked_acc_num
                )
                session.add(payout_p)

            # Payment Record
            stmt_pay = select(Payment).where(Payment.user_id == user.id)
            pay_p = (await session.execute(stmt_pay)).scalar_one_or_none()
            if not pay_p:
                pay_p = Payment(
                    user_id=user.id,
                    amount=5000.0,
                    payment_method="BANK_TRANSFER",
                    payment_status="APPROVED"
                )
                session.add(pay_p)

        await session.commit()
        logger.info("Production member profile auto-seed completed successfully.")
        
        # Write latest snapshot
        await BackupService.backup_all_members_to_json()
