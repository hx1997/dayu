from decompile.ir.nac.types import NAddressCodeType
from decompile.ir.nac.base import NAddressCode


class UncondThrowNAC(NAddressCode):
    """throw exception"""

    type = NAddressCodeType.UNCOND_THROW

    def __init__(self, exception,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._exception = exception

    @property
    def args(self):
        return [self._exception]

    @property
    def exception(self):
        return self._exception

    @exception.setter
    def exception(self, value):
        self._exception = value

    def get_uses(self):
        return self._arg_uses(self._exception)

    def replace_arg(self, idx, value):
        if idx == 0:
            self._exception = value
        else:
            raise IndexError(f'UncondThrowNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._exception = fn(self._exception)

    def __str__(self):
        return self.format_nac_str_with_label(f'throw {self._exception}')
