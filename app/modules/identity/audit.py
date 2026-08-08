import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.context import correlation_id_var, request_id_var
from app.modules.identity.models import AuditEvent


def write_audit(
    db: Session,
    *,
    action: str,
    summary: str,
    result: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        result=result,
        request_id=request_id_var.get(),
        correlation_id=correlation_id_var.get(),
        ip_address=ip_address,
        metadata_json=metadata,
    )
    db.add(event)
    return event
