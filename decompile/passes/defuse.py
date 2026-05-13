from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType
from decompile.method_pass import MethodPass
from pandasm.insn import PandasmInsnArgument


class DefUseAnalysis(MethodPass):
    def run_on_method(self, method: IRMethod):
        # compute def and use sets for all blocks
        for block in method.blocks:
            self.analyze_block(block)

    def analyze_block(self, block: IRBlock):
        defs, uses = set(), set()
        for insn in block.insns:
            if insn.type == NAddressCodeType.UNKNOWN:
                self.analyze_unknown(insn, defs, uses)
            else:
                for d in insn.get_defs():
                    if d not in uses:
                        defs.add(d)
                for u in insn.get_uses():
                    if u not in defs:
                        uses.add(u)

        block.defs, block.uses = defs, uses
        return defs, uses

    def analyze_unknown(self, insn, defs, uses):
        """
        for UNKNOWN NACs, since we don't know what this NAC does, we must assume the worst scenario:
        all operands involved are defined, but no operand is used (i.e. all killed without regeneration)
        """
        for operand in insn.args:
            # some heuristics to infer what type this operand is
            if operand == 'acc':
                acc = PandasmInsnArgument('acc')
                defs.add(acc)
            elif operand.startswith('a') or operand.startswith('v'):
                reg = PandasmInsnArgument('reg', operand)
                defs.add(reg)
            elif operand.startswith('0x') or operand.startswith('"') or operand.startswith('jump_label') or operand.startswith('com.'):
                # immediates, strings, jump labels and functions are constants, so these are not targets of our analysis
                pass
