from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCode, NAddressCodeType
from decompile.method_pass import MethodPass


class VariableAllocation(MethodPass):
    def __init__(self, rename_func_args):
        self.cur_var_no = -1
        self.reg2var_map = {}
        self.rename_func_args = rename_func_args

    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            self.run_on_block(block)

        self.add_declarations(method)

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
            self.process_arg(real_arg)

    def process_arg(self, real_arg):
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
                elif self.rename_func_args:
                    if real_arg.value not in self.reg2var_map:
                        new_arg_no = int(real_arg.value[1:]) - 3
                        self.reg2var_map[real_arg.value] = f'a{new_arg_no}'
                    real_arg.type = 'var'
                    real_arg.value = self.reg2var_map[real_arg.value]
        elif real_arg.type == 'tmp':
            if real_arg.value not in self.reg2var_map:
                self.reg2var_map[real_arg.value] = self.alloc_var()
            real_arg.type = 'var'
            real_arg.value = self.reg2var_map[real_arg.value]
        elif real_arg.type == 'expr':
            for expr_arg in real_arg.value:
                self.process_arg(expr_arg)
        elif real_arg.type.startswith('lexenv'):
            # add lexenv to reg2var_map so that it can be added to the forward declarations
            if real_arg.type not in self.reg2var_map:
                self.reg2var_map[real_arg.type] = real_arg.type

    def alloc_var(self):
        self.cur_var_no += 1
        return f'v{self.cur_var_no}'

    def add_declarations(self, method: IRMethod):
        entry_block = method.blocks[0]
        decl_vars = list(self.reg2var_map.values())
        if len(decl_vars) > 0:
            decl_stmt = f'let {", ".join(decl_vars)}'
            declare_insn = NAddressCode(decl_stmt, [], nac_type=NAddressCodeType.UNKNOWN)
            entry_block.insert_insn(declare_insn, 0)
