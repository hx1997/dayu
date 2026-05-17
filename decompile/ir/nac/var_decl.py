from decompile.ir.nac.types import NAddressCodeType
from decompile.ir.nac.base import NAddressCode


class VarDeclNAC(NAddressCode):
    """let var1, var2, ..."""

    type = NAddressCodeType.VAR_DECL

    def __init__(self, var_names,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._var_names = list(var_names)

    @property
    def args(self):
        return list(self._var_names)

    @property
    def var_names(self):
        return self._var_names

    @var_names.setter
    def var_names(self, value):
        self._var_names = list(value)

    def replace_arg(self, idx, value):
        self._var_names[idx] = value

    def remap_args(self, fn):
        self._var_names = [fn(v) for v in self._var_names]

    def __str__(self):
        return self.format_nac_str_with_label(
            f'let {", ".join([str(a) for a in self._var_names])}'
        )
