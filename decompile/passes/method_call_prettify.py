from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType
from decompile.method_pass import MethodPass


class MethodCallPrettify(MethodPass):
    """
    turn "this.v0 = func(FunctionObject, NewTarget, this, ...)" into "this.v0 = func(this, ...)"
    """
    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            self.run_on_block(block)

    def run_on_block(self, block: IRBlock):
        for insn in block.insns:
            if insn.type == NAddressCodeType.CALL:
                if len(insn.call_args) < 2:  # func(FunctionObject, NewTarget, ...), at least two call args
                    continue
                if insn.call_args[0].type == 'FunctionObject' and insn.call_args[1].type == 'NewTarget':
                    insn.call_args = insn.call_args[2:]
