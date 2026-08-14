# FEG FPL v1.0 — COMPLETE TELEGRAM FPL COMMUNITY, COMPETITION, PAYMENT & AUTOMATION SYSTEM

MASTER BUILD SPECIFICATION FOR ANTIGRAVITY

Build a production-ready Telegram-based Fantasy Premier League community and competition management platform called:

FEG FPL

The entire member experience must be centered around Telegram.

The system should consist of:
* Telegram Bot
* Telegram Community
* Telegram Announcement Channel
* Telegram Admin DM Dashboard
* Optional Telegram Mini App/member dashboard
* FEG Backend
* Database
* FPL Engine
* Live Match Engine
* Player Statistics Engine
* Content Engine
* Payment Verification Engine
* Referral Engine
* Reward Engine
* Community Access Engine
* Competition Tracking Engine
* Automated Graphic Generation Engine
* Notification Engine
* Audit/Security Engine

The system must be modular so that future features can be added without rewriting the entire application.

---

## 1. CORE BUSINESS MODEL
FEG FPL is a paid Fantasy Premier League community competition.
Registration fee: ₦5,000
Payment method: BANK TRANSFER ONLY (No card payment gateway required in v1).
Members transfer ₦5,000 to the currently configured FEG receiving bank account.
An authorised FEG administrator manually verifies the payment from the proof submitted by the member.
Once approved:
1. Registration becomes APPROVED.
2. The member receives a one-time Telegram community access link.
3. The member joins the Telegram community.
4. The bot/community sends a welcome message.
5. The member is instructed to join the official FEG Classic and H2H FPL competitions.
6. The member receives both FPL Invite Link and FPL Invite Code.
7. The member chooses whichever method they prefer.
8. The FEG system tracks the member using their FPL ID.

---

## 2. COMPETITION STRUCTURE
A. CLASSIC LEAGUE (Starts GW4) - Season-long FPL Classic League.
B. H2H LEAGUE (Starts GW4) - Head-to-Head FPL competition.
C. FEG CUP - Starts in 2nd half of season (configured GW), using eligible Classic members (no separate registration).

---

## 3. IDENTIFIERS
- FEG MEMBER ID (FEG-2026-XXXXXX)
- TELEGRAM ID (numeric string/int)
- FPL ID (manager/team numerical ID)
- FPL LEAGUE ID (Classic/H2H league ID)
- FPL INVITE CODE & LINK

---

## 4. MEMBER REGISTRATION & FLOW
1. /start -> Welcome screen with ₦5,000 fee info.
2. Full Name prompt -> Member inputs name.
3. Telegram ID -> Automatically captured from update (no manual typing).
4. FPL ID -> Member enters FPL ID (with guide on how to find it) -> FPL ID validated via FPL API engine.
5. Payout Bank Details -> Bank name, Account name, Account number (encrypted at rest, masked in dashboards).
6. Payment Screen -> Display configured FEG receiving bank account.
7. Payment Proof -> Member uploads receipt screenshot.
8. Admin DM Review -> Admins receive approval notification with proof photo & member details.
9. Approval -> payment_status = APPROVED, registration_status = APPROVED, generate single-use/member-specific Telegram join link.
10. Community Entry -> Welcome message with FPL Classic & H2H links/codes.

---

## 5. REWARDS & REFERRALS
- Personal referral deep-links (`/start ref_XXXX`).
- Milestones: 3 refs -> ₦2,000; 5 refs -> ₦4,000; 7 refs -> ₦6,000; 10 refs -> ₦10,000 (only highest milestone paid).
- Manager of the Week: ₦1,000.
- Public communication rule: ₦150,000+ pool.

---

## 6. ADMIN SYSTEM
- Super Admin (`ADMIN_SUPER_ID`): Complete oversight, overrides, system settings.
- Finance Admin (`ADMIN_FINANCE_ID`): Payments, payouts, member bank detail review.
- Content Admin (`ADMIN_CONTENT_ID`): FPL content, live updates, statistics, graphics.
- Security: Identified purely by numeric Telegram IDs. All actions logged in `audit_logs`.

---

## 7. AUTOMATION & ENGINES
- FPL Engine (lookup, sync, rate limits, caching, provider abstraction).
- Live Match Engine (fixtures, events, live points).
- Statistics & Content Engines (previews, reviews, captain picks, differentials, injuries, price alerts, memes).
- Automated Graphic Engine (Team of the Gameweek image generation).
- Notification & Audit Engines.

---

## 8. PHASES OVERVIEW
- Phase 1: Project Scaffolding
- Phase 2: Database Schema & Migrations
- Phase 3: Telegram Bot Core & Admin Auth Architecture
- Phase 4-7: Member Registration, Bank Payment Verification, Role Permissions & Community Access
- Phase 8-10: FPL Joining, FPL Engine & Member Dashboard
- Phase 11-13: Admin DM Dashboard, Referral Engine & Reward System
- Phase 14-17: Stats, Live Match, Content Engine & Graphic Generation
- Phase 18-22: Cup Activation, Notifications, Audit, Testing & Production Setup
