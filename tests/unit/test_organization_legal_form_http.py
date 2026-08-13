import asyncio
import json

from app.main import organization_legal_form_error_handler
from app.modules.organizations.service import OrganizationLegalFormError


def test_organization_legal_form_error_maps_to_422() -> None:
    response = asyncio.run(
        organization_legal_form_error_handler(
            None,  # type: ignore[arg-type]
            OrganizationLegalFormError("Недопустимый реквизит для выбранного типа организации"),
        )
    )

    assert response.status_code == 422
    assert json.loads(response.body) == {
        "detail": "Недопустимый реквизит для выбранного типа организации"
    }
