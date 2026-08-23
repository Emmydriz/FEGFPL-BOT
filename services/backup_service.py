import os
import json
import logging
from typing import List, Dict, Any
from sqlalchemy import select
from database.db import get_db_session
from database.models import User, FPLProfile, PayoutAccount, Payment
from database.crypto import encrypt_string, decrypt_string, mask_account_number

logger = logging.getLogger("feg_fpl")
BACKUP_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "members_backup.json")


class BackupService:
    @classmethod
    async def backup_all_members_to_json(cls):
        """
        Exports all user, FPL profile, and bank payout records to a persistent JSON backup file
        (data/members_backup.json) so no data is ever lost during redeploys.
        """
        try:
            os.makedirs(os.path.dirname(BACKUP_FILE_PATH), exist_ok=True)
            async with get_db_session() as session:
                stmt = select(User).order_by(User.id.asc())
                users = (await session.execute(stmt)).scalars().all()

                backup_list: List[Dict[str, Any]] = []
                for u in users:
                    stmt_f = select(FPLProfile).where(FPLProfile.user_id == u.id)
                    fpl = (await session.execute(stmt_f)).scalar_one_or_none()

                    stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == u.id)
                    payout = (await session.execute(stmt_p)).scalar_one_or_none()

                    dec_acc = ""
                    if payout and payout.encrypted_account_number:
                        try:
                            dec_acc = decrypt_string(payout.encrypted_account_number)
                        except Exception:
                            dec_acc = payout.masked_account_number or ""

                    item = {
                        "feg_member_id": u.feg_member_id,
                        "telegram_id": u.telegram_id,
                        "telegram_username": u.telegram_username,
                        "full_name": u.full_name,
                        "registration_status": u.registration_status,
                        "account_status": u.account_status,
                        "referral_code": u.referral_code,
                        "fpl_id": fpl.fpl_id if fpl else None,
                        "manager_name": fpl.manager_name if fpl else None,
                        "team_name": fpl.team_name if fpl else None,
                        "classic_status": fpl.classic_status if fpl else "PENDING",
                        "h2h_status": fpl.h2h_status if fpl else "PENDING",
                        "bank_name": payout.bank_name if payout else None,
                        "account_name": payout.account_name if payout else None,
                        "account_number": dec_acc or (payout.masked_account_number if payout else None)
                    }
                    backup_list.append(item)

                with open(BACKUP_FILE_PATH, "w", encoding="utf-8") as f:
                    json.dump(backup_list, f, indent=2, ensure_ascii=False)

                logger.info(f"Successfully backed up {len(backup_list)} member records to {BACKUP_FILE_PATH}")
        except Exception as e:
            logger.error(f"Failed to backup members to JSON: {e}")

    @classmethod
    async def restore_members_from_json_if_needed(cls):
        """
        Restores members from data/members_backup.json if present on bot startup.
        """
        if not os.path.exists(BACKUP_FILE_PATH):
            logger.info("No members_backup.json file found for auto-restoration.")
            return

        try:
            with open(BACKUP_FILE_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)

            if not records or not isinstance(records, list):
                return

            logger.info(f"Restoring {len(records)} member records from {BACKUP_FILE_PATH}...")
            async with get_db_session() as session:
                for data in records:
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
                            telegram_username=data.get("telegram_username"),
                            full_name=data["full_name"],
                            registration_status=data.get("registration_status", "COMMUNITY_ACCESS_GRANTED"),
                            account_status=data.get("account_status", "ACTIVE"),
                            referral_code=data.get("referral_code", f"FEG-REF-{tid}")
                        )
                        session.add(user)
                        await session.flush()
                    else:
                        user.feg_member_id = mid
                        user.telegram_id = tid
                        if data.get("telegram_username"):
                            user.telegram_username = data["telegram_username"]
                        user.full_name = data["full_name"]
                        user.registration_status = data.get("registration_status", "COMMUNITY_ACCESS_GRANTED")

                    # FPL Profile
                    if data.get("fpl_id"):
                        stmt_f = select(FPLProfile).where(FPLProfile.user_id == user.id)
                        fpl_p = (await session.execute(stmt_f)).scalar_one_or_none()

                        if not fpl_p:
                            fpl_p = FPLProfile(
                                user_id=user.id,
                                fpl_id=data["fpl_id"],
                                manager_name=data.get("manager_name", user.full_name),
                                team_name=data.get("team_name", "FEG FC"),
                                classic_status=data.get("classic_status", "VERIFIED"),
                                h2h_status=data.get("h2h_status", "VERIFIED")
                            )
                            session.add(fpl_p)
                        else:
                            fpl_p.fpl_id = data["fpl_id"]
                            fpl_p.manager_name = data.get("manager_name", user.full_name)
                            fpl_p.team_name = data.get("team_name", "FEG FC")
                            fpl_p.classic_status = data.get("classic_status", "VERIFIED")
                            fpl_p.h2h_status = data.get("h2h_status", "VERIFIED")

                    # Payout Account
                    if data.get("account_number") and data.get("bank_name"):
                        stmt_p = select(PayoutAccount).where(PayoutAccount.user_id == user.id)
                        payout_p = (await session.execute(stmt_p)).scalar_one_or_none()

                        raw_acc = str(data["account_number"])
                        enc_num = encrypt_string(raw_acc)
                        masked_num = mask_account_number(raw_acc)

                        if not payout_p:
                            payout_p = PayoutAccount(
                                user_id=user.id,
                                bank_name=data["bank_name"],
                                account_name=data.get("account_name", user.full_name),
                                encrypted_account_number=enc_num,
                                masked_account_number=masked_num
                            )
                            session.add(payout_p)
                        else:
                            payout_p.bank_name = data["bank_name"]
                            payout_p.account_name = data.get("account_name", user.full_name)
                            payout_p.encrypted_account_number = enc_num
                            payout_p.masked_account_number = masked_num

                    # Payment
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
                    else:
                        pay_p.payment_status = "APPROVED"

                await session.commit()
                logger.info("JSON member backup restoration completed successfully.")
        except Exception as e:
            logger.error(f"Failed to restore members from JSON: {e}")
