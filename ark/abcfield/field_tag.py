from enum import IntEnum


class FieldTag(IntEnum):
    NOTHING = 0
    INT_VALUE = 1
    VALUE = 2
    RUNTIME_ANNOTATIONS = 3
    ANNOTATIONS = 4
    RUNTIME_TYPE_ANNOTATION = 5
    TYPE_ANNOTATION = 6
