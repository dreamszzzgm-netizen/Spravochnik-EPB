import enum


class OrganizationType(enum.StrEnum):
    LEGAL_ENTITY = "legal_entity"
    INDIVIDUAL_ENTREPRENEUR = "individual_entrepreneur"
    BRANCH = "branch"


class IdentifierType(enum.StrEnum):
    INN = "inn"
    KPP = "kpp"
    OGRN = "ogrn"
    OGRNIP = "ogrnip"
    EXTERNAL_ID = "external_id"
