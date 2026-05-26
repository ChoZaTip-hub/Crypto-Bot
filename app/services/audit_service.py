"""Audit logging service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditEventType
from app.db.repositories.audit_repo import AuditRepository
from app.utils.serialization import dumps_json


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = AuditRepository(session)

    async def log(
        self,
        event_type: AuditEventType | str,
        correlation_id: str,
        payload: dict,
    ) -> None:
        await self._repo.log_event(
            {
                "correlation_id": correlation_id,
                "event_type": str(event_type),
                "payload_json": dumps_json(payload),
            }
        )
