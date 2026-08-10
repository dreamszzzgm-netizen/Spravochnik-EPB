import enum


class TechnicalDeviceType(enum.StrEnum):
    PRESSURE_VESSEL = "pressure_vessel"
    PIPELINE = "pipeline"
    LIFTING_MECHANISM = "lifting_mechanism"
    OTHER = "other"
