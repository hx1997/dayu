from enum import IntEnum, auto


class NAddressCodeType(IntEnum):
    """
    NACs can take on one of several forms:
        (1) x = y bop z
        (2) x = uop y
        (3) x = y
        (4) jump L
        (5) if x rop y jump L
        (6) x = y(z1, z2, ...)
        (7) return x
        (8) throw x
        (9) if x rop y throw y
        (10) import x as y from z
        (11) let x
    (1)-(3) are ASSIGN type, (4), UNCOND_JUMP type, (5), COND_JUMP type, (6), CALL type, (7), RETURN type,
    (8), UNCOND_THROW type, (9), COND_THROW type, (10), IMPORT type, and (11), VAR_DECL type;
    anything else (e.g., raw IR instructions) is UNKNOWN type.
    """
    ASSIGN = auto()
    UNCOND_JUMP = auto()
    COND_JUMP = auto()
    CALL = auto()
    RETURN = auto()
    UNCOND_THROW = auto()
    COND_THROW = auto()
    IMPORT = auto()
    VAR_DECL = auto()
    UNKNOWN = auto()


RELATIONAL_OPS = {
    '==': '!=',
    '!=': '==',
    '<': '>=',
    '>': '<=',
    '<=': '>',
    '>=': '<',
    '===': '!==',
    '!==': '===',
    'in': '',
    'instanceof': '',
}
