from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.analytics.management import build_management_summary
from app.modules.analytics.repository import load_management_input
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/management")
def management_report(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Management reports are available to administrators only",
        )
    data = load_management_input(db)
    return build_management_summary(data, today=date.today())
