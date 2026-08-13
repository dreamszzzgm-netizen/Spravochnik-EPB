from app.modules.expertises.enums import ExpertiseStatus

INITIAL_STATUS = ExpertiseStatus.PREPARATION

EXPERTISE_TRANSITIONS: dict[ExpertiseStatus, set[ExpertiseStatus]] = {
    ExpertiseStatus.PREPARATION: {ExpertiseStatus.DOCUMENT_COLLECTION},
    ExpertiseStatus.DOCUMENT_COLLECTION: {ExpertiseStatus.INSPECTION},
    ExpertiseStatus.INSPECTION: {ExpertiseStatus.CONCLUSION_PREPARATION},
    ExpertiseStatus.CONCLUSION_PREPARATION: {ExpertiseStatus.INTERNAL_APPROVAL},
    ExpertiseStatus.INTERNAL_APPROVAL: {ExpertiseStatus.READY_FOR_REGISTRATION},
    ExpertiseStatus.READY_FOR_REGISTRATION: {ExpertiseStatus.RTN_REVIEW},
    ExpertiseStatus.RTN_REVIEW: {
        ExpertiseStatus.REGISTERED,
        ExpertiseStatus.RTN_REWORK,
    },
    ExpertiseStatus.RTN_REWORK: {ExpertiseStatus.READY_FOR_REGISTRATION},
    ExpertiseStatus.REGISTERED: {ExpertiseStatus.RECEIVED_BY_CUSTOMER},
    ExpertiseStatus.RECEIVED_BY_CUSTOMER: {ExpertiseStatus.COMPLETED},
}


def can_transition(source: ExpertiseStatus, target: ExpertiseStatus) -> bool:
    return target in EXPERTISE_TRANSITIONS.get(source, set())
