from copy import copy

from decompile.dec_pass import Pass
from decompile.ir.basicblock import IRBlock
from decompile.ir.builder import IRBuilder
from decompile.ir.nac import NAddressCode, NAddressCodeType
from decompile.ir.insn_enum import mnemonic2lifter_map
from decompile.ir.irclass import IRClass
from decompile.ir.method import IRMethod
from decompile.ir.module import IRModule
from pandasm.method import PandasmMethod
from pandasm.pa_class import PandasmClass
from pandasm.reader import PandasmReader


class RawIR2LLIR(Pass):
    def __init__(self):
        self.module = IRModule()

    def run_on_method(self, method: IRMethod):
        builder = IRBuilder(self.module)
        for block in method.blocks:
            builder.set_insert_point(block)
            block_insns_copy = copy(block.insns)
            block.clear_insns()
            for insn in block_insns_copy:
                if insn.op in mnemonic2lifter_map:
                    # lift each instruction
                    lifter = mnemonic2lifter_map[insn.op]
                    lifter(insn, builder)
                else:
                    # print(f'Unknown instruction: {insn.mnemonic}')
                    nac = NAddressCode(insn.op, insn.args, NAddressCodeType.UNKNOWN, label_name=insn.label)
                    builder.insert(nac)
                    print(f'[{self.__class__.__name__}] warning: UNKNOWN NAC "{insn.op}" encountered in method {method.name}; analysis may be wrong!')

        # print(f'{method.name}:')
        # for nac in irblock.insns:
        #     print(f'\t{nac}')

