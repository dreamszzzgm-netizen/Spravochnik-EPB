import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.custom_fields.service import CustomFieldService
from app.modules.identity.models import Employee, User
from app.modules.identity.security import hash_password
from app.modules.opo.models import HazardSign
from app.modules.organizations.models import OrganizationType

pytestmark = pytest.mark.integration


STAGE3_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.cookies.get("spravoshnik_session")


def _create_org(client: TestClient, token: str, legal_name: str, short_name: str) -> dict:
    resp = client.post(
        "/api/organizations",
        json={
            "legal_name": legal_name,
            "short_name": short_name,
            "organization_type": OrganizationType.LEGAL_ENTITY.value,
        },
        cookies={"spravoshnik_session": token},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_opos(client: TestClient, token: str, org_id: str, reg_num: str, **kw) -> dict:
    payload = {
        "name": f"OPO {reg_num}",
        "registration_number": reg_num,
        "hazard_class": "hazard_class_2",
        "address": "Test Address",
        "registration_date": "2024-01-15",
        "owner_organization_id": org_id,
        "operating_organization_id": org_id,
    }
    payload.update(kw)
    resp = client.post(
        "/api/opo",
        json=payload,
        cookies={"spravoshnik_session": token},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_device(client: TestClient, token: str, name: str, **kw) -> dict:
    payload: dict = {
        "name": name,
        "device_type": "other",
    }
    payload.update(kw)
    resp = client.post(
        "/api/technical-devices",
        json=payload,
        cookies={"spravoshnik_session": token},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_building(client: TestClient, token: str, name: str, **kw) -> dict:
    payload: dict = {
        "name": name,
        "building_type": "other",
    }
    payload.update(kw)
    resp = client.post(
        "/api/buildings",
        json=payload,
        cookies={"spravoshnik_session": token},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 401/403/404 HTTP tests
# ---------------------------------------------------------------------------
class TestUnauthenticated:
    def test_opo_list_401(self, client: TestClient):
        resp = client.get("/api/opo")
        assert resp.status_code == 401

    def test_technical_device_list_401(self, client: TestClient):
        resp = client.get("/api/technical-devices")
        assert resp.status_code == 401

    def test_building_list_401(self, client: TestClient):
        resp = client.get("/api/buildings")
        assert resp.status_code == 401

    def test_custom_fields_get_401(self, client: TestClient):
        resp = client.get(f"/api/custom-fields/values/opo/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_reference_401(self, client: TestClient):
        resp = client.get("/api/reference/hazard-signs")
        assert resp.status_code == 401


class TestForbidden:
    def test_opo_create_403(self, client: TestClient, test_user: dict):
        token = _login(client, str(test_user["username"]), str(test_user["password"]))
        resp = client.post(
            "/api/opo",
            json={
                "name": "X",
                "registration_number": "F-001",
                "hazard_class": "hazard_class_1",
                "address": "A",
                "registration_date": "2024-01-15",
                "owner_organization_id": str(uuid.uuid4()),
                "operating_organization_id": str(uuid.uuid4()),
            },
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 403

    def test_td_create_403(self, client: TestClient, test_user: dict):
        token = _login(client, str(test_user["username"]), str(test_user["password"]))
        resp = client.post(
            "/api/technical-devices",
            json={"name": "X", "device_type": "other"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 403

    def test_building_create_403(self, client: TestClient, test_user: dict):
        token = _login(client, str(test_user["username"]), str(test_user["password"]))
        resp = client.post(
            "/api/buildings",
            json={"name": "X", "building_type": "other"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 403


class TestNotFound:
    def test_opo_unknown_uuid_404(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        resp = client.get(
            f"/api/opo/{uuid.uuid4()}",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404

    def test_td_unknown_uuid_404(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        resp = client.get(
            f"/api/technical-devices/{uuid.uuid4()}",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404

    def test_building_unknown_uuid_404(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        resp = client.get(
            f"/api/buildings/{uuid.uuid4()}",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404

    def test_deleted_opo_get_404(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "DelOPO Org", "DEL")
        opo = _create_opos(client, token, org["id"], "DEL-GET-001")
        client.delete(
            f"/api/opo/{opo['id']}",
            cookies={"spravoshnik_session": token},
        )
        resp = client.get(
            f"/api/opo/{opo['id']}",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404

    def test_deleted_td_get_404(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "DelTD Org", "DTD")
        device = _create_device(client, token, "DeleteMe", organization_id=org["id"])
        client.delete(
            f"/api/technical-devices/{device['id']}",
            cookies={"spravoshnik_session": token},
        )
        resp = client.get(
            f"/api/technical-devices/{device['id']}",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404

    def test_deleted_building_get_404(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "DelBld Org", "DBL")
        building = _create_building(client, token, "DeleteMe", organization_id=org["id"])
        client.delete(
            f"/api/buildings/{building['id']}",
            cookies={"spravoshnik_session": token},
        )
        resp = client.get(
            f"/api/buildings/{building['id']}",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Restore tests
# ---------------------------------------------------------------------------
class TestRestore:
    def test_restore_opo(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "RestoreOPO Org", "RST")
        opo = _create_opos(client, token, org["id"], "RST-001")
        client.delete(f"/api/opo/{opo['id']}", cookies={"spravoshnik_session": token})
        resp = client.post(
            f"/api/opo/{opo['id']}/restore",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        resp = client.get(f"/api/opo/{opo['id']}", cookies={"spravoshnik_session": token})
        assert resp.status_code == 200

    def test_restore_td(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "RestoreTD Org", "RTD")
        device = _create_device(client, token, "RestoreMe", organization_id=org["id"])
        client.delete(
            f"/api/technical-devices/{device['id']}", cookies={"spravoshnik_session": token}
        )
        resp = client.post(
            f"/api/technical-devices/{device['id']}/restore",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        resp = client.get(
            f"/api/technical-devices/{device['id']}", cookies={"spravoshnik_session": token}
        )
        assert resp.status_code == 200

    def test_restore_building(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "RestoreBld Org", "RBL")
        building = _create_building(client, token, "RestoreMe", organization_id=org["id"])
        client.delete(f"/api/buildings/{building['id']}", cookies={"spravoshnik_session": token})
        resp = client.post(
            f"/api/buildings/{building['id']}/restore",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        resp = client.get(
            f"/api/buildings/{building['id']}", cookies={"spravoshnik_session": token}
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# RED — PATCH semantics (section 6-7)
# ---------------------------------------------------------------------------
class TestPATCHSemantics:
    def test_patch_td_name_preserves_opo(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "PATCH-OPO Org", "POP")
        opo = _create_opos(client, token, org["id"], "PATCH-OPO-001")
        device = _create_device(
            client, token, "Linked", opo_id=opo["id"], organization_id=org["id"]
        )
        resp = client.patch(
            f"/api/technical-devices/{device['id']}",
            json={"name": "Renamed"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == "Renamed"
        assert data["opo_id"] == opo["id"], "opo_id must be preserved when omitted in PATCH"

    def test_patch_td_name_preserves_serial(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "PATCH-SER Org", "PSE")
        device = _create_device(
            client, token, "Linked", serial_number="SN-001", organization_id=org["id"]
        )
        resp = client.patch(
            f"/api/technical-devices/{device['id']}",
            json={"name": "RenamedOnly"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        assert resp.json()["serial_number"] == "SN-001", (
            "serial_number must be preserved when omitted in PATCH"
        )

    def test_patch_td_opo_null_clears_opo(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "PATCH-NULL Org", "PNU")
        opo = _create_opos(client, token, org["id"], "PATCH-NULL-001")
        device = _create_device(
            client, token, "Linked", opo_id=opo["id"], organization_id=org["id"]
        )
        resp = client.patch(
            f"/api/technical-devices/{device['id']}",
            json={"opo_id": None},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["opo_id"] is None, "explicit opo_id=null must clear OPO association"

    def test_patch_td_serial_null_clears_serial(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "PATCH-SN Org", "PSN")
        device = _create_device(
            client, token, "Linked", serial_number="SN-CLEAR", organization_id=org["id"]
        )
        resp = client.patch(
            f"/api/technical-devices/{device['id']}",
            json={"serial_number": None},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["serial_number"] is None, "explicit serial_number=null must clear serial"

    def test_patch_building_name_preserves_opo(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "PATCH-BLD Org", "PBL")
        opo = _create_opos(client, token, org["id"], "PATCH-BLD-001")
        building = _create_building(
            client, token, "Linked", opo_id=opo["id"], organization_id=org["id"]
        )
        resp = client.patch(
            f"/api/buildings/{building['id']}",
            json={"name": "Renamed"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        assert resp.json()["opo_id"] == opo["id"], "opo_id must be preserved when omitted in PATCH"

    def test_patch_building_opo_null_clears_opo(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "PATCH-BNU Org", "PBN")
        opo = _create_opos(client, token, org["id"], "PATCH-BNU-001")
        building = _create_building(
            client, token, "Linked", opo_id=opo["id"], organization_id=org["id"]
        )
        resp = client.patch(
            f"/api/buildings/{building['id']}",
            json={"opo_id": None},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        assert resp.json()["opo_id"] is None, "explicit opo_id=null must clear OPO association"


# ---------------------------------------------------------------------------
# RED — Organization ownership (section 2-4, 16)
# ---------------------------------------------------------------------------
class TestOrganizationOwnership:
    def test_standalone_td_in_org_filter(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "StandaloneTD Org", "STD")
        _create_device(client, token, "Standalone", organization_id=org["id"])
        resp = client.get(
            f"/api/technical-devices?organization_id={org['id']}",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) >= 1, "standalone device without OPO must appear in org filter"
        assert any(d["name"] == "Standalone" for d in items)

    def test_opo_linked_td_in_org_filter(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "LinkedTD Org", "LTD")
        opo = _create_opos(client, token, org["id"], "LTD-OPO-001")
        _create_device(client, token, "Linked", opo_id=opo["id"], organization_id=org["id"])
        resp = client.get(
            f"/api/technical-devices?organization_id={org['id']}",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert any(d["name"] == "Linked" for d in items), (
            "OPO-linked device must appear in same org's filter"
        )

    def test_standalone_building_in_org_filter(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "StandaloneBld Org", "SBL")
        _create_building(client, token, "Standalone", organization_id=org["id"])
        resp = client.get(
            f"/api/buildings?organization_id={org['id']}",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert len(items) >= 1, "standalone building without OPO must appear in org filter"
        assert any(b["name"] == "Standalone" for b in items)

    def test_opo_linked_building_in_org_filter(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "LinkedBld Org", "LBL")
        opo = _create_opos(client, token, org["id"], "LBL-OPO-001")
        _create_building(client, token, "Linked", opo_id=opo["id"], organization_id=org["id"])
        resp = client.get(
            f"/api/buildings?organization_id={org['id']}",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert any(b["name"] == "Linked" for b in items), (
            "OPO-linked building must appear in same org's filter"
        )


# ---------------------------------------------------------------------------
# RED — OPO comment (section 10)
# ---------------------------------------------------------------------------
class TestOPOComment:
    def test_create_opo_with_comment_stores_comment(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "Comment Org", "COM")
        resp = client.post(
            "/api/opo",
            json={
                "name": "Commented OPO",
                "registration_number": "COM-001",
                "hazard_class": "hazard_class_1",
                "address": "Addr",
                "registration_date": "2024-01-15",
                "owner_organization_id": org["id"],
                "operating_organization_id": org["id"],
                "comment": "Important safety note",
            },
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data.get("comment") == "Important safety note", "comment must be stored and returned"

    def test_update_opo_preserves_comment_when_omitted(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "CommentUpd Org", "CUP")
        opo = _create_opos(client, token, org["id"], "COM-UPD-001", comment="original comment")
        resp = client.patch(
            f"/api/opo/{opo['id']}",
            json={"name": "Renamed"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        assert resp.json().get("comment") == "original comment", (
            "comment must be preserved when omitted in PATCH"
        )

    def test_update_opo_null_clears_comment(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "CommentClr Org", "CCL")
        opo = _create_opos(client, token, org["id"], "COM-CLR-001", comment="to be cleared")
        resp = client.patch(
            f"/api/opo/{opo['id']}",
            json={"comment": None},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        assert resp.json().get("comment") is None, "explicit comment=null must clear comment"


# ---------------------------------------------------------------------------
# RED — OPO registration_date contract (section 11)
# ---------------------------------------------------------------------------
class TestOPORegistrationDate:
    def test_create_opo_explicit_date(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "RegDate Org", "RGD")
        resp = client.post(
            "/api/opo",
            json={
                "name": "Explicit Date",
                "registration_number": "RGD-001",
                "hazard_class": "hazard_class_1",
                "address": "Addr",
                "owner_organization_id": org["id"],
                "operating_organization_id": org["id"],
                "registration_date": "2023-06-15",
            },
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["registration_date"] == "2023-06-15"


# ---------------------------------------------------------------------------
# RED — Custom field entity existence (section 8-9)
# ---------------------------------------------------------------------------
class TestCustomFieldEntityValidation:
    @pytest.fixture(autouse=True)
    def _cf_defs(self, db_session: Session) -> dict[str, dict]:
        employee = Employee(full_name="CF Actor")
        db_session.add(employee)
        db_session.flush()
        user = User(
            employee_id=employee.id,
            username="cf-actor",
            password_hash=hash_password("Strong-password-123!"),
            is_active=True,
            is_superuser=True,
        )
        db_session.add(user)
        db_session.commit()
        svc = CustomFieldService()
        actor_id = user.id
        defs: dict[str, dict] = {}
        for code, name, etype in [
            ("cf_ent_exist", "Exists", "opo"),
            ("cf_ent_nonex", "Nonex", "opo"),
            ("cf_ent_del", "Deleted", "opo"),
            ("cf_td_nonex", "TD Nonex", "technical_device"),
            ("cf_td_val", "TD Valid", "technical_device"),
            ("cf_bld_val", "Bld Valid", "building"),
            ("cf_uns", "Unsupported", "opo"),
        ]:
            d = svc.create_definition(
                db_session,
                actor_id=actor_id,
                code=code,
                name=name,
                entity_type=etype,
                field_type="text",
            )
            defs[code] = {"id": str(d.id), "code": code, "entity_type": etype}
        return defs

    def test_set_value_for_existing_opo(self, client: TestClient, superuser: dict, _cf_defs):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "CF-ENT Org", "CFE")
        opo = _create_opos(client, token, org["id"], "CF-ENT-001")
        resp = client.put(
            f"/api/custom-fields/values/opo/{opo['id']}/{_cf_defs['cf_ent_exist']['id']}",
            json={"value": "real entity"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"

    def test_set_value_for_nonexistent_opo_404(self, client: TestClient, superuser: dict, _cf_defs):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        _create_org(client, token, "CF-NE Org", "CFN")
        resp = client.put(
            f"/api/custom-fields/values/opo/{uuid.uuid4()}/{_cf_defs['cf_ent_nonex']['id']}",
            json={"value": "orphan"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404, f"expected 404, got {resp.status_code}: {resp.text}"

    def test_set_value_for_deleted_opo_404(self, client: TestClient, superuser: dict, _cf_defs):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "CF-DEL Org", "CFD")
        opo = _create_opos(client, token, org["id"], "CF-DEL-001")
        client.delete(f"/api/opo/{opo['id']}", cookies={"spravoshnik_session": token})
        resp = client.put(
            f"/api/custom-fields/values/opo/{opo['id']}/{_cf_defs['cf_ent_del']['id']}",
            json={"value": "after delete"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404, f"expected 404, got {resp.status_code}: {resp.text}"

    def test_set_value_for_nonexistent_td_404(self, client: TestClient, superuser: dict, _cf_defs):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        _create_org(client, token, "CF-TD Org", "CFT")
        resp = client.put(
            f"/api/custom-fields/values/technical_device/{uuid.uuid4()}/{_cf_defs['cf_td_nonex']['id']}",
            json={"value": "orphan"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404, f"expected 404, got {resp.status_code}: {resp.text}"

    def test_set_value_with_valid_td(self, client: TestClient, superuser: dict, _cf_defs):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "CF-TDV Org", "CTV")
        device = _create_device(client, token, "CF Device", organization_id=org["id"])
        resp = client.put(
            f"/api/custom-fields/values/technical_device/{device['id']}/{_cf_defs['cf_td_val']['id']}",
            json={"value": "valid td"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200, resp.text

    def test_set_value_with_valid_building(self, client: TestClient, superuser: dict, _cf_defs):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "CF-BLV Org", "CBV")
        building = _create_building(client, token, "CF Building", organization_id=org["id"])
        resp = client.put(
            f"/api/custom-fields/values/building/{building['id']}/{_cf_defs['cf_bld_val']['id']}",
            json={"value": "valid building"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200, resp.text

    def test_get_values_nonexistent_entity_404(self, client: TestClient, superuser: dict, _cf_defs):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        resp = client.get(
            f"/api/custom-fields/values/opo/{uuid.uuid4()}",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 404, f"expected 404, got {resp.status_code}: {resp.text}"

    def test_unsupported_entity_type_422(self, client: TestClient, superuser: dict, _cf_defs):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        resp = client.put(
            f"/api/custom-fields/values/magical_entity/{uuid.uuid4()}/{_cf_defs['cf_uns']['id']}",
            json={"value": "nope"},
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 422, f"expected 422, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# RED — Search and pagination (section 15)
# ---------------------------------------------------------------------------
class TestSearchPagination:
    def test_opo_search_by_name(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "Search Org", "SRC")
        _create_opos(client, token, org["id"], "SRCH-001", name="UniqueName")
        _create_opos(client, token, org["id"], "SRCH-002", name="OtherName")
        resp = client.get(
            "/api/opo?q=UniqueName",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "UniqueName"

    def test_opo_search_by_reg_number(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "RegSearch Org", "RGS")
        _create_opos(client, token, org["id"], "REG-SRCH-001")
        _create_opos(client, token, org["id"], "REG-SRCH-002")
        resp = client.get(
            "/api/opo?q=REG-SRCH-001",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert len(items) == 1

    def test_opo_organization_filter(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org_a = _create_org(client, token, "OrgA", "OA")
        org_b = _create_org(client, token, "OrgB", "OB")
        _create_opos(client, token, org_a["id"], "FILT-A-001")
        _create_opos(client, token, org_b["id"], "FILT-B-001")
        resp = client.get(
            f"/api/opo?organization_id={org_a['id']}",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["registration_number"] == "FILT-A-001"

    def test_opo_pagination(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "Page Org", "PAG")
        for i in range(5):
            _create_opos(client, token, org["id"], f"PAGE-{i:03d}")
        resp = client.get(
            "/api/opo?page_size=2&page=1",
            cookies={"spravoshnik_session": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1

    def test_td_organization_includes_standalone(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "TDFilter Org", "TDF")
        _create_device(client, token, "Standalone", organization_id=org["id"])
        resp = client.get(
            f"/api/technical-devices?organization_id={org['id']}",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert any(d["name"] == "Standalone" for d in items)

    def test_td_opo_filter(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "TDOPO Org", "TDO")
        opo_a = _create_opos(client, token, org["id"], "TDO-A-001")
        opo_b = _create_opos(client, token, org["id"], "TDO-B-001")
        _create_device(client, token, "InA", opo_id=opo_a["id"], organization_id=org["id"])
        _create_device(client, token, "InB", opo_id=opo_b["id"], organization_id=org["id"])
        resp = client.get(
            f"/api/technical-devices?opo_id={opo_a['id']}",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "InA"

    def test_td_search(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "TDSearch Org", "TDS")
        _create_device(client, token, "AlphaDevice", organization_id=org["id"])
        _create_device(client, token, "BetaDevice", organization_id=org["id"])
        resp = client.get(
            "/api/technical-devices?q=Alpha",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "AlphaDevice"

    def test_td_pagination(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "TDPage Org", "TDP")
        for i in range(3):
            _create_device(client, token, f"TD-{i}", organization_id=org["id"])
        resp = client.get(
            "/api/technical-devices?page_size=2&page=1",
            cookies={"spravoshnik_session": token},
        )
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    def test_building_search(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "BldSearch Org", "BLS")
        _create_building(client, token, "AlphaBuilding", organization_id=org["id"])
        _create_building(client, token, "BetaBuilding", organization_id=org["id"])
        resp = client.get(
            "/api/buildings?q=Alpha",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "AlphaBuilding"

    def test_building_organization_includes_standalone(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "BldFilter Org", "BLF")
        _create_building(client, token, "Standalone Bld", organization_id=org["id"])
        resp = client.get(
            f"/api/buildings?organization_id={org['id']}",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert any(b["name"] == "Standalone Bld" for b in items)

    def test_building_opo_filter(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "BldOPO Org", "BLO")
        opo = _create_opos(client, token, org["id"], "BLO-A-001")
        _create_building(client, token, "Linked Bld", opo_id=opo["id"], organization_id=org["id"])
        resp = client.get(
            f"/api/buildings?opo_id={opo['id']}",
            cookies={"spravoshnik_session": token},
        )
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Linked Bld"

    def test_building_pagination(self, client: TestClient, superuser: dict):
        token = _login(client, str(superuser["username"]), str(superuser["password"]))
        org = _create_org(client, token, "BldPage Org", "BLP")
        for i in range(3):
            _create_building(client, token, f"BLD-{i}", organization_id=org["id"])
        resp = client.get(
            "/api/buildings?page_size=2&page=1",
            cookies={"spravoshnik_session": token},
        )
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3


# ---------------------------------------------------------------------------
# RED — Deterministic UUID (section 13)
# ---------------------------------------------------------------------------
class TestDeterministicUUID:
    def test_deterministic_uuid_exact(self, db_session: Session):
        expected = uuid.uuid5(STAGE3_NS, "explosive")
        sign = db_session.query(HazardSign).where(HazardSign.code == "explosive").one()
        assert sign.id == expected, f"expected {expected}, got {sign.id}"

    def test_deterministic_consistency(self, db_session: Session):
        signs = db_session.query(HazardSign).all()
        for sign in signs:
            expected = uuid.uuid5(STAGE3_NS, sign.code)
            assert sign.id == expected, f"UUID mismatch for code={sign.code}"
