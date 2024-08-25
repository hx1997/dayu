from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCode, NAddressCodeType
from decompile.method_pass import MethodPass


class VariableAllocation(MethodPass):
    def __init__(self):
        self.cur_var_no = -1
        self.reg2var_map = {}

    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            self.run_on_block(block)

    def run_on_block(self, block: IRBlock):
        for insn in block.insns:
            self.run_on_insn(insn)

    def run_on_insn(self, insn: NAddressCode):
        if insn.type == NAddressCodeType.UNKNOWN:
            return
        for arg in insn.args:
            real_arg = arg
            while real_arg.ref_obj:
                real_arg = real_arg.ref_obj
            if real_arg.type == 'acc':
                if 'acc' not in self.reg2var_map:
                    self.reg2var_map['acc'] = self.alloc_var()
                real_arg.type = 'var'
                real_arg.value = self.reg2var_map['acc']
            elif real_arg.type == 'reg':
                if real_arg.value[0] != 'a':
                    if real_arg.value not in self.reg2var_map:
                        self.reg2var_map[real_arg.value] = self.alloc_var()
                    real_arg.type = 'var'
                    real_arg.value = self.reg2var_map[real_arg.value]
                else:
                    if real_arg.value == 'a0':
                        real_arg.type = 'var'
                        real_arg.value = 'FunctionObject'
                    elif real_arg.value == 'a1':
                        real_arg.type = 'var'
                        real_arg.value = 'NewTarget'
                    elif real_arg.value == 'a2':
                        real_arg.type = 'var'
                        real_arg.value = 'this'
            elif real_arg.type == 'tmp':
                if real_arg.value not in self.reg2var_map:
                    self.reg2var_map[real_arg.value] = self.alloc_var()
                real_arg.type = 'var'
                real_arg.value = self.reg2var_map[real_arg.value]

    def alloc_var(self):
        self.cur_var_no += 1
        return f'v{self.cur_var_no}'
