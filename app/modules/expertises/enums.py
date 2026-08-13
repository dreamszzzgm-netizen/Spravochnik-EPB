import enum


class ExpertiseParticipantRole(enum.StrEnum):
    EXPERT = "expert"
    SPECIALIST = "specialist"


class ExpertiseStatus(enum.StrEnum):
    PREPARATION = "preparation"
    DOCUMENT_COLLECTION = "document_collection"
    INSPECTION = "inspection"
    CONCLUSION_PREPARATION = "conclusion_preparation"
    INTERNAL_APPROVAL = "internal_approval"
    READY_FOR_REGISTRATION = "ready_for_registration"
    RTN_REVIEW = "rtn_review"
    RTN_REWORK = "rtn_rework"
    REGISTERED = "registered"
    RECEIVED_BY_CUSTOMER = "received_by_customer"
    COMPLETED = "completed"
