from decompile.ir.nac.types import NAddressCodeType
from decompile.ir.nac.base import NAddressCode


class ReturnNAC(NAddressCode):
    """return retval"""

    type = NAddressCodeType.RETURN

    def __init__(self, retval,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._retval = retval

    @property
    def args(self):
        return [self._retval]

    @property
    def retval(self):
        return self._retval

    @retval.setter
    def retval(self, value):
        self._retval = value

    def get_uses(self):
        return self._arg_uses(self._retval)

    def replace_arg(self, idx, value):
        if idx == 0:
            self._retval = value
        else:
            raise IndexError(f'ReturnNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._retval = fn(self._retval)

    def __str__(self):
        return self.format_nac_str_with_label(f'return {self._retval}')
