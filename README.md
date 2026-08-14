# FEG FPL — Complete Telegram FPL Community, Competition, Payment & Automation Platform

FEG FPL is a production-ready, modular Telegram-based Fantasy Premier League community and competition management platform.

---

## 🌟 Feature Overview & Completed Architecture

### 1. Core Member Registration & Payment Flow (Phases 1–7)
- **Automatic Telegram ID Capture**: Automatically captures numeric Telegram IDs (`update.effective_user.id`) to avoid user entry errors.
- **FPL ID Validation**: Integrates live FPL API (`FPLService.validate_fpl_id`) to verify manager name and team name.
- **Duplicate FPL Guard**: Prevents linking an FPL ID already registered to another FEG account.
- **Encrypted Payout Bank Details**: Encrypts member bank details at rest using AES-256 Fernet with masked fallback (`••••4821`).
- **Manual Bank Transfer Verification**: Displays active receiving account for ₦5,000 registration fee.
- **Versioned Payment Accounts**: Preserves historical receiving account configurations (`PaymentAccountConfig`).
- **Admin Review DM Workflow**: Sends DM alerts to Finance Admin (`ADMIN_FINANCE_ID`) & Super Admin (`ADMIN_SUPER_ID`) with receipt photo and `[✅ APPROVE]` / `[❌ REJECT]` buttons.
- **Single-Use Community Access**: Generates member-specific, single-use Telegram community invite links (`CommunityService.create_one_time_invite`).

### 2. Competition Structure & Joining Verification (Phase 8–10)
- **Classic League (GW4 Start)**: Configured via `FPL_CLASSIC_LEAGUE_ID`, code, and link.
- **H2H League (GW4 Start)**: Configured via `FPL_H2H_LEAGUE_ID`, code, and link.
- **League Membership Verification**: Automated API verification (`FPLService.check_league_membership`).
- **Interactive Dashboards**: `/profile`, `/dashboard`, `/classic`, `/h2h`, `/cup`.

### 3. Admin DM Dashboard & Audit System (Phase 11)
- **Role-Based Admin Access**: Numeric Telegram ID authentication (`ADMIN_SUPER_ID`, `ADMIN_FINANCE_ID`, `ADMIN_CONTENT_ID`).
- **Security Guard**: Blocks unauthorized Telegram IDs and logs `UNAUTHORISED_ADMIN_ACCESS_ATTEMPT` in `audit_logs`.
- **Receiving Account Versioning**: `/set_pay_account BankName | AccountName | AccountNumber` with auto-versioning.

### 4. Personal Referral Engine & Milestone Rewards (Phase 12)
- **Personal Deep Links**: `t.me/FEGFPL_Bot?start=ref_FEG-REF-XXXXXX`.
- **Verified Referral Rule**: Referral counts only AFTER referred member's ₦5,000 payment is approved.
- **Milestone Rewards**:
  - 3 referrals ➡️ ₦2,000
  - 5 referrals ➡️ ₦4,000
  - 7 referrals ➡️ ₦6,000
  - 10 referrals ➡️ ₦10,000
- **Highest Milestone Rule**: Only the highest achieved milestone is eligible/paid.

### 5. Reward Payout & Manager of the Week (Phase 13)
- **Manager of the Week**: ₦1,000 reward for top weekly scorer.
- **Public Prize Communication Rule**: Displays `₦150,000+` pool without public internal breakdown.
- **Admin Payout Marking**: Admin DM alert with member payout bank details. Admin transfers money manually and marks paid with payment reference.

### 6. Media Content & Automated Graphic Generation (Phases 14–17)
- **Content Engine**: `/captain`, `/differentials`, `/pricewatch`, `/preview`.
- **Automated Graphic Engine**: Generates high-resolution PNG images for **Team of the Gameweek** (`services/graphic_engine.py`).

### 7. Mid-Season Cup Activation (Phase 18)
- **Automatic Cup Tracking**: Activates at configured gameweek (GW19) using existing Classic participants.

---

## 💻 Local PC Setup & Execution Guide

### 1. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Create `.env` based on `.env.example`:
```env
APP_ENV=development
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
DATABASE_URL=sqlite+aiosqlite:///./feg_fpl.db

FEG_REGISTRATION_FEE=5000
FEG_PAYMENT_BANK=Access Bank
FEG_PAYMENT_ACCOUNT_NAME=FEG FPL
FEG_PAYMENT_ACCOUNT_NUMBER=0123456789

ADMIN_SUPER_ID=YOUR_NUMERIC_TELEGRAM_ID
ADMIN_FINANCE_ID=FINANCE_ADMIN_TELEGRAM_ID
ADMIN_CONTENT_ID=CONTENT_ADMIN_TELEGRAM_ID

FPL_CLASSIC_LEAGUE_ID=123456
FPL_CLASSIC_INVITE_CODE=ABC123
FPL_CLASSIC_INVITE_LINK=https://fantasy.premierleague.com/leagues/auto-join/ABC123

FPL_H2H_LEAGUE_ID=789012
FPL_H2H_INVITE_CODE=XYZ789
FPL_H2H_INVITE_LINK=https://fantasy.premierleague.com/leagues/auto-join/XYZ789

FEG_START_GAMEWEEK=4
FEG_CUP_START_GAMEWEEK=19
SECRET_KEY=supersecretkey_change_me_in_production
```

### 3. Run Automated Test Suite
```powershell
python -m pytest tests/
```

### 4. Start Telegram Bot Engine
```powershell
python -m bot.main
```

---

## 🧪 Verification Matrix

| Module | Test File | Test Cases Passed |
| :--- | :--- | :--- |
| Database & Models | `tests/test_db.py` | 4 |
| Admin Authentication | `tests/test_admin_auth.py` | 2 |
| Member Registration | `tests/test_registration.py` | 3 |
| Payment Review | `tests/test_payment.py` | 2 |
| Referral Milestones | `tests/test_referrals.py` | 1 |
| Rewards & Payouts | `tests/test_rewards.py` | 1 |
| Graphic Generation | `tests/test_graphic_engine.py` | 1 |
| **Total** | | **14 / 14 Passed** |
