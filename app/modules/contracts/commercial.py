import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractAddendumStatus
from app.modules.contracts.models import Contract, ContractAddendum, ContractItem

MONEY_QUANTUM = Decimal("0.01")


def calculate_effective_amount(
    db: Session,
    contract_id: uuid.UUID,
    *,
    pending_delta: Decimal = Decimal("0.00"),
) -> Decimal:
    item_total = db.scalar(
        sa.select(
            sa.func.coalesce(sa.func.sum(ContractItem.price), Decimal("0.00"))
        ).where(
            ContractItem.contract_id == contract_id,
            ContractItem.deleted_at.is_(None),
        )
    )
    signed_delta_total = db.scalar(
        sa.select(
            sa.func.coalesce(
                sa.func.sum(ContractAddendum.amount_delta),
                Decimal("0.00"),
            )
        ).where(
            ContractAddendum.contract_id == contract_id,
            ContractAddendum.deleted_at.is_(None),
            ContractAddendum.status == ContractAddendumStatus.SIGNED,
        )
    )
    return (
        Decimal(item_total or 0)
        + Decimal(signed_delta_total or 0)
        + Decimal(pending_delta)
    ).quantize(MONEY_QUANTUM)


def recalculate_effective_amount(db: Session, contract: Contract) -> Decimal:
    amount = calculate_effective_amount(db, contract.id)
    contract.amount = amount
    db.flush()
    return amount
