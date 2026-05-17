from decompile.ir.nac.types import NAddressCodeType
from decompile.ir.nac.base import NAddressCode


class UnknownNAC(NAddressCode):
    """Raw IR instruction or structured control-flow text (while {, }, etc.).
    Keeps a real mutable args list permanently — this is intentional since raw IR
    operands are inherently positional."""

    type = NAddressCodeType.UNKNOWN

    def __init__(self, op, args=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self.args = list(args) if args is not None else []

    def replace_arg(self, idx, value):
        self.args[idx] = value

    def remap_args(self, fn):
        for i in range(len(self.args)):
            self.args[i] = fn(self.args[i])

    def __str__(self):
        s = f'{self.op} {", ".join([str(a) for a in self.args])}'
        return self.format_nac_str_with_label(s)
