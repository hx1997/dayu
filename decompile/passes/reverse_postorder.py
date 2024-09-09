from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.method_pass import MethodPass


class ReversePostorder(MethodPass):
    def __init__(self):
        self.vis = set()
        self.postorder = []

    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            if block not in self.vis:
                self.rpo(block)
        return self.postorder[::-1]

    def rpo(self, block: IRBlock):
        if block in self.vis:
            return
        self.vis.add(block)

        for succ in block.successors:
            self.rpo(succ)

        self.postorder.append(block)
