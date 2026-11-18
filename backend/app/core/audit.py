"""Audit logging helper."""
import json
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def record_audit(
    session: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
) -> AuditLog:
    """Record an action in the immutable audit log table.

    Args:
        session: Database session.
        action: Short action description (e.g. 'CREATE', 'UPDATE', 'POST', 'CANCEL').
        entity_type: Target table or entity name (e.g. 'order', 'production_run').
        entity_id: Primary key of target entity.
        user_id: ID of the user performing the action.
        before: Optional state before change.
        after: Optional state after change.

    Returns:
        The created AuditLog instance.
    """
    before_json = json.dumps(before, default=str) if before is not None else None
    after_json = json.dumps(after, default=str) if after is not None else None

    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before_json,
        after_json=after_json,
        at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.flush()
    return entry
