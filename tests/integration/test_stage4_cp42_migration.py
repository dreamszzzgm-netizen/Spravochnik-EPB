import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.contracts.enums import ContractAddendumStatus
from app.modules.contracts.models import Contract, ContractAddendum, ContractSuspension


def test_cp42_models_expose_expected_contract_fields() -> None:
    assert hasattr(Contract, "original_end_date")
    assert ContractSuspension.__tablename__ == "contract_suspensions"
    assert ContractAddendum.__tablename__ == "contract_addenda"
    assert [status.value for status in ContractAddendumStatus] == [
        "draft",
        "approval",
        "signed",
        "cancelled",
    ]


def test_cp42_database_objects_exist(db_session: Session) -> None:
    inspector = sa.inspect(db_session.get_bind())
    assert "contract_suspensions" in inspector.get_table_names()
    assert "contract_addenda" in inspector.get_table_names()
    index_names = {
        index["name"] for index in inspector.get_indexes("contract_suspensions")
    }
    assert "uq_contract_suspensions_one_open" in index_names
