from decompile.ir.nac.types import NAddressCodeType, RELATIONAL_OPS
from decompile.ir.nac.base import NAddressCode


class CondJumpNAC(NAddressCode):
    """if (cond1) jump target  /  if (cond1 op cond2) jump target"""

    type = NAddressCodeType.COND_JUMP

    def __init__(self, op, cond1, target, cond2=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self._cond1 = cond1
        self._cond2 = cond2
        self._target = target

    @property
    def args(self):
        if self._cond2 is not None:
            return [self._cond1, self._cond2, self._target]
        return [self._cond1, self._target]

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
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        self._target = value

    def get_uses(self):
        uses = self._arg_uses(self._cond1)
        if self._cond2 is not None:
            uses.extend(self._arg_uses(self._cond2))
        # target is a label; include it for behavioural consistency with the old defuse.py
        uses.extend(self._arg_uses(self._target))
        return uses

    def replace_arg(self, idx, value):
        if idx == 0:
            self._cond1 = value
        elif idx == 1:
            if self._cond2 is not None:
                self._cond2 = value
            else:
                self._target = value
        elif idx == 2:
            self._target = value
        else:
            raise IndexError(f'CondJumpNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._cond1 = fn(self._cond1)
        if self._cond2 is not None:
            self._cond2 = fn(self._cond2)
        self._target = fn(self._target)

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
        if self._cond2 is not None:
            s = f'if ({self._cond1} {self.op} {self._cond2}) jump {self._target}'
        else:
            s = f'if ({self._cond1}) jump {self._target}'
        return self.format_nac_str_with_label(s)
