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
    (1)-(3) are ASSIGN type, (4), UNCOND_JUMP type, (5), COND_JUMP type, (6), CALL type, (7), RETURN type,
    (8), UNCOND_THROW type, and (9), COND_THROW type; anything else (e.g., raw IR instructions) is UNKNOWN type.
    """
    ASSIGN = auto()
    UNCOND_JUMP = auto()
    COND_JUMP = auto()
    CALL = auto()
    RETURN = auto()
    UNCOND_THROW = auto()
    COND_THROW = auto()
    UNKNOWN = auto()

class NAddressCode:
    relational_op = {
        '==': '!=',
        '!=': '==',
        '<': '>=',
        '>': '<=',
        '<=': '>',
        '>=': '<',
        '===': '!==',
        '!==': '===',
        'in': '',
        'instanceof': ''
    }

    def __init__(self, op, args=None, nac_type=NAddressCodeType.ASSIGN, parent_block=None, label_name='', comment=''):
        """
        :param op: operation on the right-hand side of ASSIGNs or in the condition of COND_JUMPs
        :param args: list of argument(s), specifically:
            args[0]: for ASSIGNs, this is the left-hand side argument; for UNCOND_JUMPs, the jump target;
                for COND_JUMPs, the first argument in the condition
            args[1]: for ASSIGNs, this is the first right-hand side argument; for COND_JUMP (5), the jump target;
                for COND_JUMP (6), the second argument in the condition
            args[2]: for ASSIGN (1), this is the second right-hand side argument; for COND_JUMP (6), the jump target
            args[n]: can you guess? (hint: CALL type)
        :param nac_type: type of this NAC instruction
        """
        self.op = op
        self.args = args
        self.type = nac_type
        self.parent_block = parent_block
        if self.parent_block:
            self.parent_block.insert_insn(self)
        self.label = label_name
        self.comment = comment

    def __str__(self):
        if self.type == NAddressCodeType.ASSIGN:
            if len(self.args) > 3 or len(self.args) < 2:
                raise SyntaxError(f"{self.__class__.__name__}: ASSIGN NACs can't take > 3 or < 2 arguments")
            elif len(self.args) == 3:
                return self.format_nac_str_with_label(f'{self.args[0]} = {self.args[1]} {self.op} {self.args[2]}')
            elif len(self.args) == 2:
                return self.format_nac_str_with_label(f'{self.args[0]} = {self.op + (" " if self.op else "")}{self.args[1]}')
        elif self.type == NAddressCodeType.UNCOND_JUMP:
            return self.format_nac_str_with_label(f'jump {self.args[0]}')
        elif self.type == NAddressCodeType.COND_JUMP:
            if len(self.args) > 3 or len(self.args) < 2:
                raise SyntaxError(f"{self.__class__.__name__}: COND_JUMP NACs can't take > 3 or < 2 arguments")
            elif len(self.args) == 3:
                return self.format_nac_str_with_label(f'if ({self.args[0]} {self.op} {self.args[1]}) jump {self.args[2]}')
            elif len(self.args) == 2:
                return self.format_nac_str_with_label(f'if ({self.args[0]}) jump {self.args[1]}')
        elif self.type == NAddressCodeType.CALL:
            call_args = [str(arg) for arg in self.args[2:]]
            return self.format_nac_str_with_label(f'{self.args[0]} = {self.args[1]}({", ".join(call_args)})')
        elif self.type == NAddressCodeType.RETURN:
            if len(self.args) > 1 or len(self.args) == 0:
                raise SyntaxError(f"{self.__class__.__name__}: RETURN NACs can only take exactly one argument")
            elif len(self.args) == 1:
                return self.format_nac_str_with_label(f'return {self.args[0]}')
        elif self.type == NAddressCodeType.UNCOND_THROW:
            if len(self.args) > 1 or len(self.args) == 0:
                raise SyntaxError(f"{self.__class__.__name__}: UNCOND_THROW NACs can only take exactly one argument")
            return self.format_nac_str_with_label(f'throw {self.args[0]}')
        elif self.type == NAddressCodeType.COND_THROW:
            if len(self.args) != 3:
                raise SyntaxError(f"{self.__class__.__name__}: COND_THROW NACs can only take exactly three arguments")
            else:
                return self.format_nac_str_with_label(f'if ({self.args[0]} {self.op} {self.args[1]}) throw {self.args[2]}')
        elif self.type == NAddressCodeType.UNKNOWN:
            return self.format_nac_str_with_label(f'{self.op} {", ".join([str(arg) for arg in self.args])}')

    def format_nac_str_with_label(self, nac_str):
        if self.label:
            if self.comment:
                return f'{self.label}:\n{nac_str}  /* {self.comment} */'
            else:
                return f'{self.label}:\n{nac_str}'
        elif self.comment:
            return f'{nac_str}  /* {self.comment} */'
        else:
            return nac_str

    def erase_from_parent(self):
        if not self.parent_block:
            raise Exception(f'{self.__class__.__name__}: this instruction has no parent')
        self.parent_block.remove_insn(self)

    def is_relational_operation(self):
        return self.type in [NAddressCodeType.ASSIGN, NAddressCodeType.COND_JUMP, NAddressCodeType.COND_THROW] and self.op in self.relational_op

    def reverse_relational_operation(self):
        assert self.is_relational_operation()
        reverse = self.relational_op[self.op]
        if reverse != '':
            self.op = reverse
            return True
        else:
            return False
