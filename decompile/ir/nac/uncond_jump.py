from decompile.ir.nac.types import NAddressCodeType
from decompile.ir.nac.base import NAddressCode


class UncondJumpNAC(NAddressCode):
    """jump target"""

    type = NAddressCodeType.UNCOND_JUMP

    def __init__(self, target,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._target = target

    @property
    def args(self):
        return [self._target]

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        self._target = value

    def get_uses(self):
        return self._arg_uses(self._target)

    def replace_arg(self, idx, value):
        if idx == 0:
            self._target = value
        else:
            raise IndexError(f'UncondJumpNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._target = fn(self._target)

    def __str__(self):
        return self.format_nac_str_with_label(f'jump {self._target}')
