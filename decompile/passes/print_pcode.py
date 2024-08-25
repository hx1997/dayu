from decompile.ir.basicblock import IRBlock
from decompile.ir.builder import IRBuilder
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCode, NAddressCodeType
from decompile.method_pass import MethodPass


class PrintPcode(MethodPass):
    def __init__(self):
        self.vis = set()

    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            if block not in self.vis:
                self.dfs(block)

    def dfs(self, block: IRBlock):
        if block in self.vis:
            return
        self.vis.add(block)

        for insn in block.insns:
            print(insn)

        # prioritize the successor that isn't the jump target, because we have to make sure this block
        # is followed immediately by its successor(s) in the final sequential pseudocode
        # e.g.
        #           |block A (ending in a conditional jump to C)|
        #          /         \
        #      |block B|   |block C (jump target)|
        #          \         /
        #           |block D|
        # if we were to perform dfs on block C before B, we would have
        #   (block A)
        #   (block C)
        #   (block D)
        #   (block B)
        # when A doesn't take the jump to C, it should go to B, but in the sequential pseudocode it wrongly
        # falls through to C instead
        successors_target = []
        successors_nontarget = []
        for succ in block.successors:
            if succ.insns[0].label == '':
                successors_nontarget.append(succ)
            else:
                successors_target.append(succ)

        successors = successors_nontarget + successors_target
        for succ in successors:
            self.dfs(succ)
