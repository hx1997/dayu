from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType
from decompile.method_pass import MethodPass
from decompile.passes.dead_code import DeadCodeElimination


class PeepholeOptimization(MethodPass):
    def __init__(self, out_l, constrained=False):
        super().__init__()
        self.out_l = out_l
        self.constrained = constrained

    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            insn_changed = False
            first_time = True
            while insn_changed or first_time:
                insn_changed = False
                first_time = False
                old_block_insns = block.insns.copy()
                self.eliminate_redundant_load_store(block)
                self.collapse_cond_jump(block)
                if block.insns != old_block_insns:
                    insn_changed = True

    def eliminate_redundant_load_store(self, block: IRBlock):
        block_insns_copy = block.insns.copy()
        for idx, insn in enumerate(block_insns_copy):
            if idx == 0:
                continue
            # case 0: eliminate "a = a", which could result from CopyPropagation replacing copies
            # take extra care that the rhs doesn't have an operator
            if insn.type == NAddressCodeType.ASSIGN and insn.dst == insn.src and insn.op == '':
                insn.erase_from_parent()
                continue
            if self.constrained:
                # for now, all optimization cases in this method deal with instructions that have exactly two arguments
                if len(insn.args) != 2 or len(block_insns_copy[idx - 1].args) != 2:
                    continue
                if insn.type != NAddressCodeType.ASSIGN or block_insns_copy[idx - 1].type != NAddressCodeType.ASSIGN:
                    self.eliminate_stld_lexvar_pattern(idx, insn, block_insns_copy)
                    continue
            else:
                # for now, all optimization cases in this method deal with instructions that have exactly two arguments
                # in unconstrained mode, we may need to collapse method calls, so check only for ASSIGNs
                if insn.type == NAddressCodeType.ASSIGN and len(insn.args) != 2 or len(block_insns_copy[idx - 1].args) != 2:
                    continue
                if insn.type not in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL] or block_insns_copy[idx - 1].type != NAddressCodeType.ASSIGN:
                    self.eliminate_stld_lexvar_pattern(idx, insn, block_insns_copy)
                    continue
                if insn.type == NAddressCodeType.CALL:
                    continue
            if block_insns_copy[idx - 1] not in block_insns_copy[idx - 1].parent_block.insns:
                # the previous instruction could have already been eliminated in the last iteration, in which case
                # if we proceed to the following cases we'll be looking at a non-existent instruction
                continue
            # case 1: eliminate "a = b; b = a" by removing "b = a"
            elif (insn.src == block_insns_copy[idx - 1].dst and insn.dst == block_insns_copy[idx - 1].src
                  and insn.op == '' and block_insns_copy[idx - 1].op == ''):
                insn.erase_from_parent()
            # case 2: collapse "a = b; a = a['xxx']" into "a = b['xxx']"
            # take extra care that the two instructions don't both have an operator on the rhs
            elif (insn.src.ref_obj == block_insns_copy[idx - 1].dst and insn.dst == insn.src.ref_obj
                  and not (insn.op and block_insns_copy[idx - 1].op)):
                insn.src.ref_obj = block_insns_copy[idx - 1].src
                # if the first instruction has a rhs operator, copy it to the second one before erasing
                if insn.op == '':
                    insn.op = block_insns_copy[idx - 1].op
                block_insns_copy[idx - 1].erase_from_parent()
            else:
                # the following optimizations are only viable if the common variable `a` is dead after
                # the second instruction, so analyze liveness here
                if idx + 1 < len(block_insns_copy):
                    live_vars = DeadCodeElimination(self.out_l).analyze_block(block, False, block_insns_copy[idx + 1])
                    if block_insns_copy[idx - 1].dst in live_vars or block_insns_copy[idx - 1].dst.ref_obj in live_vars:
                        continue
                # case 3: collapse "a = b; c = a" into "c = b"
                # take extra care that the two instructions don't both have an operator on the rhs
                if insn.src == block_insns_copy[idx - 1].dst and not (insn.op and block_insns_copy[idx - 1].op):
                    # in constrained mode,
                    # make sure b and c don't both have a ref_obj, since we don't want "c['xxx'] = b['yyy']" just yet
                    # as it will break the three-argument form of ASSIGN NACs and complicate analysis
                    if block_insns_copy[idx - 1].src.ref_obj is None or insn.dst.ref_obj is None or not self.constrained:
                        insn.src = block_insns_copy[idx - 1].src
                        # if the first instruction has a rhs operator, copy it to the second one before erasing
                        if insn.op == '':
                            insn.op = block_insns_copy[idx - 1].op
                        block_insns_copy[idx - 1].erase_from_parent()
                # case 4: collapse "a = b; c = a['xxx']" into "c = b['xxx']"
                elif insn.src.ref_obj and insn.src.ref_obj == block_insns_copy[idx - 1].dst and not (insn.op and block_insns_copy[idx - 1].op):
                    # in constrained mode,
                    # make sure b doesn't have a ref_obj itself, since we don't want chained ref_obj just yet
                    # as it will break the three-argument form of ASSIGN NACs and complicate analysis
                    if block_insns_copy[idx - 1].src.ref_obj is None or not self.constrained:
                        insn.src.ref_obj = block_insns_copy[idx - 1].src
                        if insn.op == '':
                            insn.op = block_insns_copy[idx - 1].op
                        block_insns_copy[idx - 1].erase_from_parent()
                # case 5: collapse "a = b; a['xxx'] = c" into "b['xxx'] = c"
                elif insn.dst.ref_obj and insn.dst.ref_obj == block_insns_copy[idx - 1].dst and block_insns_copy[idx - 1].op == '':
                    # in constrained mode,
                    # make sure b doesn't have a ref_obj itself, since we don't want chained ref_obj just yet
                    # as it will break the three-argument form of ASSIGN NACs and complicate analysis
                    if block_insns_copy[idx - 1].src.ref_obj is None or not self.constrained:
                        insn.dst.ref_obj = block_insns_copy[idx - 1].src
                        block_insns_copy[idx - 1].erase_from_parent()

    def eliminate_stld_lexvar_pattern(self, idx, insn, block_insns_copy):
        """
        eliminate redundant stlexvar/ldlexvar pairs
        match the pattern:
           lexenv = func:__get_lexenv__(xxx)
           lexenv[yyy] = acc
           lexenv = func:__get_lexenv__(xxx)
           acc = lexenv[yyy]
        and eliminate the last two instructions
        """
        if idx - 3 >= 0:
            if self.check_lexvar_opt_pattern(idx, insn, block_insns_copy):
                insn.erase_from_parent()
                block_insns_copy[idx - 1].erase_from_parent()

    def check_lexvar_opt_pattern(self, idx, insn, block_insns_copy):
        if insn.type != NAddressCodeType.ASSIGN or block_insns_copy[idx - 2].type != NAddressCodeType.ASSIGN:
            return False
        if block_insns_copy[idx - 1].type != NAddressCodeType.CALL or block_insns_copy[idx - 3].type != NAddressCodeType.CALL:
            return False
        if insn.dst.type != 'acc' or insn.src.type != 'field':
            return False
        if block_insns_copy[idx - 2].dst.type != 'field' or block_insns_copy[idx - 2].src.type != 'acc':
            return False
        if not insn.src.ref_obj or insn.src.ref_obj.type != 'lexenv':
            return False
        if not block_insns_copy[idx - 2].dst.ref_obj or block_insns_copy[idx - 2].dst.ref_obj.type != 'lexenv':
            return False
        if insn.src.ref_obj.value != block_insns_copy[idx - 2].dst.ref_obj.value:
            return False
        if block_insns_copy[idx - 1].dst.type != 'lexenv' or block_insns_copy[idx - 1].func.value != '__get_lexenv__':
            return False
        if block_insns_copy[idx - 3].dst.type != 'lexenv' or block_insns_copy[idx - 3].func.value != '__get_lexenv__':
            return False
        if block_insns_copy[idx - 1].call_args[1].value != block_insns_copy[idx - 3].call_args[1].value:
            return False
        return True

    def collapse_cond_jump(self, block: IRBlock):
        """
        Collapse instruction sequences like
          acc = acc == true
          if acc != 0 jump xxx
        into
          if acc == true jump xxx
        """
        block_insns_copy = block.insns.copy()
        for idx, insn in enumerate(block_insns_copy):
            if idx == 0:
                continue
            if (insn.type not in [NAddressCodeType.COND_JUMP, NAddressCodeType.COND_THROW]
                    or block_insns_copy[idx - 1].type != NAddressCodeType.ASSIGN):
                continue
            if insn.cond1 == block_insns_copy[idx - 1].dst:
                if insn.op in ['==', '!='] and insn.cond2.type == 'zero' and block_insns_copy[idx - 1].is_relational_operation():
                    if insn.op == '==' and not block_insns_copy[idx - 1].invert_relational_operation():
                        continue
                    insn.cond1 = block_insns_copy[idx - 1].src
                    insn.op = block_insns_copy[idx - 1].op
                    insn.cond2 = block_insns_copy[idx - 1].src2
                    block_insns_copy[idx - 1].erase_from_parent()
        pass
