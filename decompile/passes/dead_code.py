from decompile.ir.basicblock import IRBlock
from decompile.ir.exception_semantics import live_before, may_throw
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType
from decompile.method_pass import MethodPass


class DeadCodeElimination(MethodPass):
    def __init__(self, out_l, exception_live=None):
        """
        :param out_l: result from LiveVariableAnalysis
        """
        super().__init__()
        self.out_l = out_l
        self.exception_live = exception_live if exception_live is not None else {}

    def run_on_method(self, method: IRMethod):
        for block in method.blocks.copy():
            self.analyze_block(block)

    def analyze_block(self, block: IRBlock, eliminate_dead_code=True, stop_after_insn=None):
        """
        For a given block, do instruction-level live variable analysis and eliminate dead definitions
        if `eliminate_dead_code` is True
        Returns variables live at block entry, or before `stop_after_insn`.
        With elimination disabled this query does not mutate instructions or CFG.
        """
        live_vars = self.out_l[block].copy()
        exception_live = self.exception_live.get(block, set())
        # Scan backwards because each instruction needs the values required by
        # both its normal continuation and an exception raised at that point.
        for insn in block.insns[::-1]:
            if insn.type == NAddressCodeType.ASSIGN:
                if eliminate_dead_code:
                    self.analyze_assign(insn, live_vars)
            live_vars = self.update_live_vars(insn, live_vars, exception_live)
            if insn == stop_after_insn:
                break

        # it could be possible that after elimination, this block is empty
        # in that case, remove this block
        # Keep an empty handler entry: removing it would also remove the only
        # named target of the exception edge.
        if eliminate_dead_code and not block.insns and not block.exception_predecessors:
            for predecessor in block.predecessors.copy():
                for successor in block.successors.copy():
                    predecessor.add_successor(successor)
            block.clear_successors()
            block.clear_predecessors()
            block.erase_from_parent()

        return live_vars

    def analyze_assign(self, insn, live_vars: set):
        # if the defined variable is not live at this point (i.e. it's not used after being defined),
        # is not a lexical variable,
        # and if it doesn't involve a reference object (see following example), eliminate it
        # Example:
        #    reg:v0['xxx'] = acc
        # the left-hand side may not be subsequently used in this method, but since it's a reference,
        # the location pointed to by reg:v0 could be accessible outside the method, and therefore
        # reg:v0['xxx'], too, could be used elsewhere outside this method, so optimizing it would be wrong
        dst = insn.get_defs()[0]
        if dst not in live_vars and dst.type != 'lexvar' and not dst.ref_obj and not may_throw(insn):
            # print(f'{insn} is dead code')
            insn.erase_from_parent()

    def update_live_vars(self, insn, live_vars: set, exception_live=None):
        return live_before(insn, live_vars, exception_live if exception_live is not None else set())
