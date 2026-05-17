from decompile.ir.nac.types import NAddressCodeType
from decompile.ir.nac.base import NAddressCode


class ImportNAC(NAddressCode):
    """import { imported } as local_name from 'module'"""

    type = NAddressCodeType.IMPORT

    def __init__(self, imported, local_name, module,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._imported = imported
        self._local_name = local_name
        self._module = module

    @property
    def args(self):
        return [self._imported, self._local_name, self._module]

    @property
    def imported(self):
        return self._imported

    @imported.setter
    def imported(self, value):
        self._imported = value

    @property
    def local_name(self):
        return self._local_name

    @local_name.setter
    def local_name(self, value):
        self._local_name = value

    @property
    def module(self):
        return self._module

    @module.setter
    def module(self, value):
        self._module = value

    def replace_arg(self, idx, value):
        if idx == 0:
            self._imported = value
        elif idx == 1:
            self._local_name = value
        elif idx == 2:
            self._module = value
        else:
            raise IndexError(f'ImportNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._imported = fn(self._imported)
        self._local_name = fn(self._local_name)
        self._module = fn(self._module)

    def __str__(self):
        s = ('import { ' + f'{self._imported}' + ' } as '
             + f"{self._local_name} from '{self._module}';")
        return self.format_nac_str_with_label(s)
