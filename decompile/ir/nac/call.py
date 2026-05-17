from decompile.ir.nac.types import NAddressCodeType
from decompile.ir.nac.base import NAddressCode


class CallNAC(NAddressCode):
    """dst = func(call_args...)"""

    type = NAddressCodeType.CALL

    def __init__(self, func, call_args, dst=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._dst = dst
        self._func = func
        self._call_args = list(call_args)

    @property
    def args(self):
        return [self._dst, self._func, *self._call_args]

    @property
    def dst(self):
        return self._dst

    @dst.setter
    def dst(self, value):
        self._dst = value

    @property
    def func(self):
        return self._func

    @func.setter
    def func(self, value):
        self._func = value

    @property
    def call_args(self):
        return self._call_args

    @call_args.setter
    def call_args(self, value):
        self._call_args = list(value)

    def get_defs(self):
        return [self._dst]

    def get_uses(self):
        uses = []
        if self._dst.ref_obj:
            uses.append(self._dst.ref_obj)
        uses.extend(self._arg_uses(self._func))
        for a in self._call_args:
            uses.extend(self._arg_uses(a))
        return uses

    def replace_arg(self, idx, value):
        if idx == 0:
            self._dst = value
        elif idx == 1:
            self._func = value
        else:
            self._call_args[idx - 2] = value

    def remap_args(self, fn):
        self._dst = fn(self._dst)
        self._func = fn(self._func)
        self._call_args = [fn(a) for a in self._call_args]

    def __str__(self):
        call_args_str = [str(a) for a in self._call_args]
        return self.format_nac_str_with_label(
            f'{self._dst} = {self._func}({", ".join(call_args_str)})'
        )
