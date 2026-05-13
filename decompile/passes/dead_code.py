from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType
from decompile.method_pass import MethodPass


class DeadCodeElimination(MethodPass):
    def __init__(self, out_l):
        """
        :param out_l: result from LiveVariableAnalysis
        """
        super().__init__()
        self.out_l = out_l

    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            self.analyze_block(block)

    def analyze_block(self, block: IRBlock, eliminate_dead_code=True, stop_after_insn=None):
        """
        For a given block, do instruction-level live variable analysis and eliminate dead definitions
        if `eliminate_dead_code` is True
        Returns the set of variables live at the end of the block, or after a given instruction specified
        by `stop_after_insn`
        """
        live_vars = self.out_l[block]
        # live variable analysis is backward, so reverse the list
        for insn in block.insns[::-1]:
            if insn.type == NAddressCodeType.ASSIGN:
                if eliminate_dead_code:
                    self.analyze_assign(insn, live_vars)
            live_vars = self.update_live_vars(insn, live_vars)
            if insn == stop_after_insn:
                break

        # it could be possible that after elimination, this block is empty
        # if so, remove this block
        if len(block.insns) == 0:
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
        if dst not in live_vars and dst.type != 'lexvar' and not dst.ref_obj:
            # print(f'{insn} is dead code')
            insn.erase_from_parent()

    def update_live_vars(self, insn, live_vars: set):
        vars_def = set(insn.get_defs())
        vars_use = set(insn.get_uses())
        return live_vars.difference(vars_def).union(vars_use)
