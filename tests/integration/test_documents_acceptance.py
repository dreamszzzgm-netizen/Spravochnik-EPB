import hashlib
import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.modules.documents.models import DocumentRequirement, OrganizationDocument
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import OPO
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization


def _login(client, credentials: dict[str, object]) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "username": credentials["username"],
            "password": credentials["password"],
        },
    )
    assert response.status_code == 200


def test_requirement_and_document_file_lifecycle(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    organization = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name="Documents Acceptance LLC",
    )
    db_session.add(organization)
    db_session.commit()

    requirement_response = client.post(
        "/api/document-requirements",
        json={
            "document_type": "insurance",
            "title": "Insurance",
            "applicability": "all",
            "required": True,
            "expiry_required": True,
            "active": True,
        },
    )
    assert requirement_response.status_code == 201

    content = b"document acceptance bytes\x00\xff"
    upload_response = client.post(
        f"/api/organizations/{organization.id}/documents",
        data={
            "document_type": "insurance",
            "title": "Insurance 2026",
            "expires_at": "2026-08-20",
        },
        files={"file": ("insurance.bin", content, "application/octet-stream")},
    )
    assert upload_response.status_code == 201, upload_response.text
    uploaded = upload_response.json()
    assert uploaded["sha256"] == hashlib.sha256(content).hexdigest()
    assert uploaded["size_bytes"] == len(content)
    assert uploaded["original_filename"] == "insurance.bin"
    assert uploaded["status"] in {"expired", "expiring_14", "expiring_40", "valid"}

    download_response = client.get(
        f"/api/organizations/{organization.id}/documents/{uploaded['id']}/download"
    )
    assert download_response.status_code == 200
    assert download_response.content == content

    delete_response = client.delete(
        f"/api/organizations/{organization.id}/documents/{uploaded['id']}"
    )
    assert delete_response.status_code == 204
    list_response = client.get(f"/api/organizations/{organization.id}/documents")
    assert list_response.status_code == 200
    assert list_response.json() == {"source_available": True, "items": []}

    document = db_session.get(OrganizationDocument, uploaded["id"])
    assert document is not None
    assert document.deleted_at is not None


def test_requirement_endpoints_are_superuser_only(client, test_user: dict[str, object]) -> None:
    _login(client, test_user)
    assert client.get("/api/document-requirements").status_code == 403


def test_management_report_uses_applicable_requirements_and_real_statuses(
    client, db_session: Session, superuser: dict[str, object]
) -> None:
    _login(client, superuser)
    without_opo = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name="Without OPO",
    )
    with_opo = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name="With OPO",
    )
    db_session.add_all([without_opo, with_opo])
    db_session.flush()
    db_session.add(
        OPO(
            name="Acceptance OPO",
            registration_number=f"ACC-{uuid.uuid4()}",
            hazard_class=HazardClass.HAZARD_CLASS_3,
            address="Acceptance address",
            registration_date=date.today(),
            owner_organization_id=with_opo.id,
            operating_organization_id=with_opo.id,
        )
    )
    db_session.add_all(
        [
            DocumentRequirement(
                document_type="company_card",
                title="Company card",
                applicability="all",
                required=True,
                expiry_required=False,
                active=True,
            ),
            DocumentRequirement(
                document_type="opo_certificate",
                title="OPO certificate",
                applicability="has_opo",
                required=True,
                expiry_required=True,
                active=True,
            ),
        ]
    )
    db_session.flush()
    today = date.today()
    db_session.add_all(
        [
            OrganizationDocument(
                organization_id=without_opo.id,
                document_type="company_card",
                title="Valid company card",
                original_filename="valid.bin",
                content_type="application/octet-stream",
                storage_key=f"{uuid.uuid4().hex}.bin",
                sha256="0" * 64,
                size_bytes=1,
            ),
            OrganizationDocument(
                organization_id=with_opo.id,
                document_type="company_card",
                title="Expiring company card",
                original_filename="expiring.bin",
                content_type="application/octet-stream",
                storage_key=f"{uuid.uuid4().hex}.bin",
                sha256="1" * 64,
                size_bytes=1,
                expires_at=today + timedelta(days=7),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/reports/management")
    assert response.status_code == 200
    documents = response.json()["documents"]
    assert documents["source_available"] is True
    assert documents["valid"] == 1
    assert documents["expiring_14"] == 1
    assert documents["missing"] == 1
    missing = [issue for issue in documents["issues"] if issue["status"] == "missing"]
    assert [issue["organization_id"] for issue in missing] == [str(with_opo.id)]
