from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType
from decompile.method_pass import MethodPass


class LiveVariableAnalysis(MethodPass):
    def run_on_method(self, method: IRMethod):
        in_block, out_block = {}, {}
        # add dummy entry and exit blocks
        entry_block = IRBlock()
        exit_block = IRBlock()
        entry_block.add_successor(method.blocks[0])
        no_successor_blocks = []
        for block in method.blocks:
            if self.is_no_successor_block(block):
                no_successor_blocks.append(block)
                block.add_successor(exit_block)

        extended_block_list = [entry_block, exit_block, *method.blocks]
        for block in extended_block_list:
            in_block[block] = set()

        in_changed = False
        first_time = True
        while in_changed or first_time:
            in_changed = False
            first_time = False
            for block in extended_block_list:
                if block != exit_block:
                    out_b = set()
                    for succ in block.successors:
                        out_b = out_b.union(in_block[succ])
                    out_block[block] = out_b
                    old_in_block = in_block.copy()
                    in_block[block] = block.uses.union(out_block[block].difference(block.defs))
                    if old_in_block != in_block:
                        in_changed = True

        # remove the dummy blocks
        method.blocks[0].remove_predecessor(entry_block)
        for block in no_successor_blocks:
            block.remove_successor(exit_block)

        return in_block, out_block

    def is_no_successor_block(self, block: IRBlock):
        return len(block.successors) == 0
