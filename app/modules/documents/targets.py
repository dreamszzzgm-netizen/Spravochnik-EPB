import uuid
from dataclasses import dataclass


class DocumentTargetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentTarget:
    organization_id: uuid.UUID | None = None
    opo_id: uuid.UUID | None = None
    technical_device_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    contract_id: uuid.UUID | None = None
    expertise_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if len(self.non_null_items()) != 1:
            raise DocumentTargetError("document target must contain exactly one target id")

    def non_null_items(self) -> tuple[tuple[str, uuid.UUID], ...]:
        return tuple(
            (name, value)
            for name, value in (
                ("organization_id", self.organization_id),
                ("opo_id", self.opo_id),
                ("technical_device_id", self.technical_device_id),
                ("building_id", self.building_id),
                ("contract_id", self.contract_id),
                ("expertise_id", self.expertise_id),
                ("task_id", self.task_id),
            )
            if value is not None
        )

    def as_link_kwargs(self) -> dict[str, uuid.UUID | None]:
        return {
            "organization_id": self.organization_id,
            "opo_id": self.opo_id,
            "technical_device_id": self.technical_device_id,
            "building_id": self.building_id,
            "contract_id": self.contract_id,
            "expertise_id": self.expertise_id,
            "task_id": self.task_id,
        }
