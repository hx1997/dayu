from decompile.ir.nac.types import NAddressCodeType, RELATIONAL_OPS
from decompile.ir.nac.base import NAddressCode


class CondThrowNAC(NAddressCode):
    """if (cond1 op cond2) throw exception"""

    type = NAddressCodeType.COND_THROW

    def __init__(self, op, cond1, cond2, exception,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self._cond1 = cond1
        self._cond2 = cond2
        self._exception = exception

    @property
    def args(self):
        return [self._cond1, self._cond2, self._exception]

    @property
    def cond1(self):
        return self._cond1

    @cond1.setter
    def cond1(self, value):
        self._cond1 = value

    @property
    def cond2(self):
        return self._cond2

    @cond2.setter
    def cond2(self, value):
        self._cond2 = value

    @property
    def exception(self):
        return self._exception

    @exception.setter
    def exception(self, value):
        self._exception = value

    def get_uses(self):
        uses = []
        for a in [self._cond1, self._cond2, self._exception]:
            uses.extend(self._arg_uses(a))
        return uses

    def replace_arg(self, idx, value):
        if idx == 0:
            self._cond1 = value
        elif idx == 1:
            self._cond2 = value
        elif idx == 2:
            self._exception = value
        else:
            raise IndexError(f'CondThrowNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._cond1 = fn(self._cond1)
        self._cond2 = fn(self._cond2)
        self._exception = fn(self._exception)

    def is_relational_operation(self):
        return self.op in RELATIONAL_OPS

    def invert_relational_operation(self):
        assert self.is_relational_operation()
        inverted = RELATIONAL_OPS[self.op]
        if inverted != '':
            self.op = inverted
            return True
        return False

    def __str__(self):
        s = f'if ({self._cond1} {self.op} {self._cond2}) throw {self._exception}'
        return self.format_nac_str_with_label(s)
