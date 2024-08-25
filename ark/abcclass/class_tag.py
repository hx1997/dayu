from enum import IntEnum


class ClassTag(IntEnum):
    NOTHING = 0
    INTERFACES = 1
    SOURCE_LANG = 2
    RUNTIME_ANNOTATION = 3
    ANNOTATION = 4
    RUNTIME_TYPE_ANNOTATION = 5
    TYPE_ANNOTATION = 6
    SOURCE_FILE = 7
