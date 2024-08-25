import typing

from decompile.ir.method_ctx import PandasmMethodContext
from pandasm.insn import PandasmInsn


class PandasmMethod:
    def __init__(self, method_name, method_return_type, method_args):
        self.name = method_name
        self.return_type = method_return_type
        self.args = method_args
        self.insns: typing.List[PandasmInsn] = []
        self._context = PandasmMethodContext(self)
