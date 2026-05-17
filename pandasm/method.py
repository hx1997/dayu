import typing

from decompile.ir.method_ctx import IRMethodContext
from pandasm.insn import PandasmInsn


class PandasmTryCatchRegion:
    """Represents a single .catchall try-catch region parsed from Panda Assembly.

    Fields correspond to the four comma-separated labels in the directive:
        .catchall try_begin, try_end, handler_begin, handler_end

    Note: handler_begin may equal try_end (degenerate case) when the handler
    block starts immediately after the try body with no intervening jmp.

    catch_type is always None for .catchall. Typed .catch directives are not
    yet supported and are silently skipped during parsing.
    """

    def __init__(self, try_begin: str, try_end: str, handler_begin: str, handler_end: str, catch_type=None):
        self.try_begin = try_begin
        self.handler_begin = handler_begin
        self.try_end = try_end
        self.handler_end = handler_end
        self.catch_type = catch_type  # None for .catchall

    def __repr__(self):
        return (f'PandasmTryCatchRegion(try_begin={self.try_begin!r}, try_end={self.try_end!r}, '
                f'handler_begin={self.handler_begin!r}, handler_end={self.handler_end!r}, '
                f'catch_type={self.catch_type!r})')


class PandasmMethod:
    def __init__(self, method_name, method_return_type, method_args):
        self.name = method_name
        self.return_type = method_return_type
        self.args = method_args
        self.insns: typing.List[PandasmInsn] = []
        self.try_catch_regions: typing.List[PandasmTryCatchRegion] = []
        self._context = IRMethodContext(self)
