from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType
from decompile.method_pass import MethodPass


class MethodCallPrettify(MethodPass):
    """
    turn "this.v0 = func(FunctionObject, NewTarget, this, ...)" into "this.v0 = func(...)"
    """
    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            self.run_on_block(block)

    def run_on_block(self, block: IRBlock):
        for insn in block.insns:
            if insn.type == NAddressCodeType.CALL:
                if len(insn.args) < 5:  # v0 = func(FunctionObject, NewTarget, this, ...), at least five arguments
                    continue
                if insn.args[2].type == 'FunctionObject' and insn.args[3].type == 'NewTarget':
                    insn.args[2:] = insn.args[5:]
