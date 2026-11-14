from decompile.ir.exception_semantics import handler_live, live_before
from decompile.ir.method import IRMethod
from decompile.method_pass import MethodPass


class LiveVariableAnalysis(MethodPass):
    def __init__(self, potentially_throwing_operations=None):
        super().__init__()
        self.potentially_throwing_operations = potentially_throwing_operations

    def run_on_method(self, method: IRMethod):
        in_block = {block: set() for block in method.blocks}
        out_block = {block: set() for block in method.blocks}
        changed = True
        while changed:
            changed = False
            for block in reversed(method.blocks):
                # Normal successors are reached after the whole block. A handler
                # can be reached in the middle of the block, so its requirements
                # are applied at each possible throwing instruction instead.
                normal_out = set()
                for successor in block.successors:
                    normal_out.update(in_block[successor])
                out_block[block] = normal_out
                exception_live = handler_live(block, in_block)
                live = normal_out
                for insn in reversed(block.insns):
                    live = live_before(insn, live, exception_live, self.potentially_throwing_operations)
                if live != in_block[block]:
                    in_block[block] = live
                    changed = True

        self.exception_live = {
            block: handler_live(block, in_block) for block in method.blocks
        }
        return in_block, out_block
