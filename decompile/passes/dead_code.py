from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType, NAddressCode
from decompile.method_pass import MethodPass
from pandasm.insn import PandasmInsnArgument


class DeadCodeElimination(MethodPass):
    def __init__(self, out_l):
        """
        :param out_l: result from LiveVariableAnalysis
        """
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
                live_vars = self.update_live_vars_for_assign(insn, live_vars)
            elif insn.type in [NAddressCodeType.UNCOND_JUMP, NAddressCodeType.UNCOND_THROW]:
                live_vars = self.update_live_vars_for_uncond_jump_throw(insn, live_vars)
            elif insn.type in [NAddressCodeType.COND_JUMP, NAddressCodeType.COND_THROW]:
                live_vars = self.update_live_vars_for_cond_jump_throw(insn, live_vars)
            elif insn.type == NAddressCodeType.RETURN:
                live_vars = self.update_live_vars_for_return(insn, live_vars)
            elif insn.type == NAddressCodeType.CALL:
                live_vars = self.update_live_vars_for_call(insn, live_vars)
            if insn == stop_after_insn:
                break

        # it could be possible that after elimination, this block is empty
        # if so, remove this block
        if len(block.insns) == 0:
            block.clear_successors()
            block.clear_predecessors()
            block.erase_from_parent()

        return live_vars

    def analyze_assign(self, insn: NAddressCode, live_vars: set):
        # if the defined variable is not live at this point (i.e. it's not used after being defined),
        # and if it doesn't involve a reference object (see following example), eliminate it
        # Example:
        #    reg:v0['xxx'] = acc
        # the left-hand side may not be subsequently used in this method, but since it's a reference,
        # the location pointed to by reg:v0 could be accessible outside the method, and therefore
        # reg:v0['xxx'], too, could be used elsewhere outside this method, so optimizing it would be wrong
        if insn.args[0] not in live_vars and not insn.args[0].ref_obj:
            # print(f'{insn} is dead code')
            insn.erase_from_parent()

    def update_live_vars_for_assign(self, insn: NAddressCode, live_vars: set):
        vars_def = {insn.args[0]}
        vars_use = {insn.args[1]}
        if insn.args[0].ref_obj:
            vars_use.add(insn.args[0].ref_obj)
        if insn.args[1].ref_obj:
            vars_use.add(insn.args[1].ref_obj)
        # for nested ExprArg
        for arg in insn.args[1:]:
            if isinstance(arg, ExprArg):
                vars_use.update(arg.get_used_args())
        if len(insn.args) == 3:
            vars_use.add(insn.args[2])
            if insn.args[2].ref_obj:
                vars_use.add(insn.args[2].ref_obj)
        live_vars = live_vars.difference(vars_def).union(vars_use)
        return live_vars

    def update_live_vars_for_uncond_jump_throw(self, insn: NAddressCode, live_vars: set):
        var_def = set()
        vars_use = {insn.args[0]}
        if insn.args[0].ref_obj:
            vars_use.add(insn.args[0].ref_obj)
        live_vars = live_vars.difference(var_def).union(vars_use)
        return live_vars

    def update_live_vars_for_cond_jump_throw(self, insn: NAddressCode, live_vars: set):
        var_def = set()
        vars_use = {insn.args[0], insn.args[1]}
        if insn.args[0].ref_obj:
            vars_use.add(insn.args[0].ref_obj)
        if insn.args[1].ref_obj:
            vars_use.add(insn.args[1].ref_obj)
        if len(insn.args) == 3:
            vars_use.add(insn.args[2])
            if insn.args[2].ref_obj:
                vars_use.add(insn.args[2].ref_obj)
        live_vars = live_vars.difference(var_def).union(vars_use)
        return live_vars

    def update_live_vars_for_return(self, insn: NAddressCode, live_vars: set):
        var_def = set()
        vars_use = {insn.args[0]}
        if insn.args[0].ref_obj:
            vars_use.add(insn.args[0].ref_obj)
        live_vars = live_vars.difference(var_def).union(vars_use)
        return live_vars

    def update_live_vars_for_call(self, insn: NAddressCode, live_vars: set):
        var_def = {insn.args[0]}
        vars_use = set()
        if insn.args[0].ref_obj:
            vars_use.add(insn.args[0].ref_obj)

        for arg in insn.args[1:]:
            vars_use.add(arg)
            # for nested ExprArg
            if isinstance(arg, ExprArg):
                vars_use.update(arg.get_used_args())
            if arg.ref_obj:
                vars_use.add(arg.ref_obj)

        live_vars = live_vars.difference(var_def).union(vars_use)
        return live_vars
