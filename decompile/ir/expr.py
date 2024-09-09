import typing

from pandasm.insn import PandasmInsnArgument


class ExprArg(PandasmInsnArgument):
    def __init__(self, arg_value: typing.List[PandasmInsnArgument], expr_type, op: str):
        if not isinstance(arg_value, list):
            raise TypeError(f'[{self.__class__.__name__}] error: arg_value must be a list')
        if expr_type == 'arith' and len(arg_value) > 2:
            raise Exception(f'[{self.__class__.__name__}] error: arithmetic ExprArgs can only take <= 2 arguments')

        super().__init__('expr', arg_value, None)
        self.expr_type = expr_type
        self.op = op

    def __str__(self):
        if self.expr_type == 'arith':
            if len(self.value) == 1:
                return f'({self.op} {str(self.value[0])})'
            elif len(self.value) == 2:
                return f'({str(self.value[0])} {self.op} {str(self.value[1])})'
        elif self.expr_type == 'call':
            call_args = [str(arg) for arg in self.value[1:]]
            return f'{self.value[0]}({", ".join(call_args)})'

    def __hash__(self):
        elems_hash = sum([elem.__hash__() for elem in self.value])
        return (self.type.__hash__() + self.expr_type.__hash__() + self.op.__hash__()
                + elems_hash + (self.ref_obj.__hash__() if self.ref_obj else '<null>'.__hash__()))

    def get_used_args(self):
        used_args = set()
        for arg in self.value:
            if isinstance(arg, ExprArg):
                used_args.update(arg.get_used_args())
            else:
                if arg.ref_obj:
                    used_args.add(arg.ref_obj)
                else:
                    used_args.add(arg)
        return used_args
