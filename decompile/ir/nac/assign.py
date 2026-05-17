from decompile.ir.nac.types import NAddressCodeType, RELATIONAL_OPS
from decompile.ir.nac.base import NAddressCode


class AssignNAC(NAddressCode):
    """x = src  /  x = op src  /  x = src op src2"""

    type = NAddressCodeType.ASSIGN

    def __init__(self, op, dst, src, src2=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self._dst = dst
        self._src = src
        self._src2 = src2

    @property
    def args(self):
        if self._src2 is not None:
            return [self._dst, self._src, self._src2]
        return [self._dst, self._src]

    @property
    def dst(self):
        return self._dst

    @dst.setter
    def dst(self, value):
        self._dst = value

    @property
    def src(self):
        return self._src

    @src.setter
    def src(self, value):
        self._src = value

    @property
    def src2(self):
        return self._src2

    @src2.setter
    def src2(self, value):
        self._src2 = value

    def get_defs(self):
        return [self._dst]

    def get_uses(self):
        uses = []
        if self._dst.ref_obj:
            uses.append(self._dst.ref_obj)
        uses.extend(self._arg_uses(self._src))
        if self._src2 is not None:
            uses.extend(self._arg_uses(self._src2))
        return uses

    def replace_arg(self, idx, value):
        if idx == 0:
            self._dst = value
        elif idx == 1:
            self._src = value
        elif idx == 2:
            self._src2 = value
        else:
            raise IndexError(f'AssignNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._dst = fn(self._dst)
        self._src = fn(self._src)
        if self._src2 is not None:
            self._src2 = fn(self._src2)

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
        if self._src2 is not None:
            s = f'{self._dst} = {self._src} {self.op} {self._src2}'
        else:
            s = f'{self._dst} = {self.op + (" " if self.op else "")}{self._src}'
        return self.format_nac_str_with_label(s)
