from app.modules.expertises.domain import (
    EXPERTISE_TRANSITIONS,
    INITIAL_STATUS,
    can_transition,
)
from app.modules.expertises.enums import ExpertiseStatus


def test_initial_status_is_preparation() -> None:
    assert INITIAL_STATUS is ExpertiseStatus.PREPARATION


def test_main_flow_transitions_are_allowed() -> None:
    flow = [
        ExpertiseStatus.PREPARATION,
        ExpertiseStatus.DOCUMENT_COLLECTION,
        ExpertiseStatus.INSPECTION,
        ExpertiseStatus.CONCLUSION_PREPARATION,
        ExpertiseStatus.INTERNAL_APPROVAL,
        ExpertiseStatus.READY_FOR_REGISTRATION,
        ExpertiseStatus.RTN_REVIEW,
        ExpertiseStatus.REGISTERED,
        ExpertiseStatus.RECEIVED_BY_CUSTOMER,
        ExpertiseStatus.COMPLETED,
    ]
    for source, target in zip(flow, flow[1:], strict=False):
        assert can_transition(source, target), f"{source.value} -> {target.value}"


def test_rtn_rework_path_is_allowed() -> None:
    assert can_transition(ExpertiseStatus.RTN_REVIEW, ExpertiseStatus.RTN_REWORK)
    assert can_transition(ExpertiseStatus.RTN_REWORK, ExpertiseStatus.READY_FOR_REGISTRATION)


def test_arbitrary_transition_is_rejected() -> None:
    assert not can_transition(
        ExpertiseStatus.PREPARATION, ExpertiseStatus.REGISTERED
    )
    assert not can_transition(
        ExpertiseStatus.PREPARATION, ExpertiseStatus.COMPLETED
    )
    assert not can_transition(
        ExpertiseStatus.COMPLETED, ExpertiseStatus.PREPARATION
    )


def test_terminal_status_has_no_outgoing_transitions() -> None:
    assert EXPERTISE_TRANSITIONS.get(ExpertiseStatus.COMPLETED, set()) == set()
