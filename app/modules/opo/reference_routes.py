from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.identity.dependencies import require_permission
from app.modules.identity.models import User
from app.modules.opo.repository import list_activity_types, list_hazard_signs
from app.modules.opo.schemas import OPOActivityTypeResponse, OPOHazardSignResponse

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("/hazard-signs", response_model=list[OPOHazardSignResponse])
def read_hazard_signs(
    _actor: User = Depends(require_permission("opo.view")),
    db: Session = Depends(get_db),
):
    return list_hazard_signs(db)


@router.get("/activity-types", response_model=list[OPOActivityTypeResponse])
def read_activity_types(
    _actor: User = Depends(require_permission("opo.view")),
    db: Session = Depends(get_db),
):
    return list_activity_types(db)


@router.get("/technical-device-types", response_model=list[str])
def read_technical_device_types(
    _actor: User = Depends(require_permission("technical_devices.view")),
):
    from app.modules.technical_devices.enums import TechnicalDeviceType

    return [t.value for t in TechnicalDeviceType]


@router.get("/building-types", response_model=list[str])
def read_building_types(
    _actor: User = Depends(require_permission("buildings.view")),
):
    from app.modules.buildings.enums import BuildingType

    return [t.value for t in BuildingType]
