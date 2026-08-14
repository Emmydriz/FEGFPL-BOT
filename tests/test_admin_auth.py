import pytest
from config.settings import settings
from services.auth_service import AuthService
from database.db import init_db, get_db_session
from database.models import AuditLog
from sqlalchemy import select


def test_numeric_telegram_admin_roles():
    # Super Admin check
    assert AuthService.get_admin_role(settings.ADMIN_SUPER_ID) == "SUPER_ADMIN"
    assert AuthService.is_authorized_admin(settings.ADMIN_SUPER_ID) is True
    assert AuthService.is_authorized_admin(settings.ADMIN_SUPER_ID, "FINANCE_ADMIN") is True

    # Finance Admin check
    assert AuthService.get_admin_role(settings.ADMIN_FINANCE_ID) == "FINANCE_ADMIN"
    assert AuthService.is_authorized_admin(settings.ADMIN_FINANCE_ID, "FINANCE_ADMIN") is True
    assert AuthService.is_authorized_admin(settings.ADMIN_FINANCE_ID, "SUPER_ADMIN") is False

    # Content Admin check
    assert AuthService.get_admin_role(settings.ADMIN_CONTENT_ID) == "CONTENT_ADMIN"
    assert AuthService.is_authorized_admin(settings.ADMIN_CONTENT_ID, "CONTENT_ADMIN") is True
    assert AuthService.is_authorized_admin(settings.ADMIN_CONTENT_ID, "FINANCE_ADMIN") is False

    # Unknown ID check (must be rejected)
    unknown_id = 999999999
    assert AuthService.get_admin_role(unknown_id) is None
    assert AuthService.is_authorized_admin(unknown_id) is False


@pytest.mark.asyncio
async def test_unauthorized_access_attempt_audit_logging():
    await init_db()

    unknown_id = 888888888
    await AuthService.log_unauthorized_attempt(
        telegram_id=unknown_id,
        action="/admin",
        details="Attempted command execution from unregistered device"
    )

    async with get_db_session() as session:
        stmt = select(AuditLog).where(AuditLog.admin_id == unknown_id)
        result = await session.execute(stmt)
        log = result.scalar_one_or_none()

        assert log is not None
        assert log.action == "UNAUTHORISED_ADMIN_ACCESS_ATTEMPT"
        assert log.role == "UNAUTHORIZED"
        assert log.target == "/admin"
