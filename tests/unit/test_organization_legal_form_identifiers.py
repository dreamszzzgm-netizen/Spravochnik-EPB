import pytest

from app.modules.organizations.enums import IdentifierType, OrganizationType
from app.modules.organizations.service import (
    OrganizationLegalFormError,
    validate_organization_legal_form,
)


def test_ip_rejects_kpp_identifier() -> None:
    with pytest.raises(OrganizationLegalFormError):
        validate_organization_legal_form(
            OrganizationType.INDIVIDUAL_ENTREPRENEUR,
            legal_address=None,
            actual_address=None,
            director_name=None,
            residence_address="residence",
            passport_details=None,
            identifiers=[
                {
                    "identifier_type": IdentifierType.KPP,
                    "identifier_value": "770101001",
                    "is_primary": False,
                }
            ],
        )


def test_legal_entity_rejects_ogrnip_identifier() -> None:
    with pytest.raises(OrganizationLegalFormError):
        validate_organization_legal_form(
            OrganizationType.LEGAL_ENTITY,
            legal_address="legal address",
            actual_address=None,
            director_name=None,
            residence_address=None,
            passport_details=None,
            identifiers=[
                {
                    "identifier_type": IdentifierType.OGRNIP,
                    "identifier_value": "326770000123456",
                    "is_primary": False,
                }
            ],
        )
