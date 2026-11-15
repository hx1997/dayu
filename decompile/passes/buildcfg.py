from decompile.ir.method import IRMethod
from decompile.method_pass import MethodPass


class BuildCFG(MethodPass):
    def run_on_method(self, method: IRMethod):
        if len(method.blocks) > 1:
            raise Exception(f'{self.__class__.__name__}: Method has more than one block, which could mean \
                a CFG has already been built. Clear it first by putting all NACs into one IRBlock.')

        original_insns = list(method.blocks[0].insns)
        insn_order = {insn: index for index, insn in enumerate(original_insns)}

        block_queue = [*method.blocks]
        while len(block_queue) > 0:
            cur_block = block_queue.pop(0)
            for i, insn in enumerate(cur_block.insns):
                branch_type = self.is_branch_insn(insn.op)
                if insn.op == 'throw':
                    if i + 1 < len(cur_block.insns):
                        new_block = cur_block.split_block(cur_block.insns[i + 1])
                        if new_block:
                            block_queue.append(new_block)
                    break
                if branch_type:
                    # if this is a branch instruction, we need to make two new nodes in the CFG
                    # first, for the next instruction (a branch instruction marks the end of a basic block,
                    # so the next one is in a new block)
                    if i+1 < len(cur_block.insns):
                        new_block = cur_block.split_block(cur_block.insns[i+1])
                        if new_block:
                            block_queue.append(new_block)

                    # second, for the branch target
                    if branch_type == 'uncond':
                        target_insn = method.get_insn_by_label(insn.args[0])
                    elif branch_type == 'cond':
                        target_insn = method.get_insn_by_label(insn.args[1])
                    if target_insn:
                        new_block = target_insn.parent_block.split_block(target_insn, extra_predecessors=[cur_block])
                        if new_block:
                            block_queue.append(new_block)

        self._split_try_region_boundaries(method)
        for index, block in enumerate(sorted(
                method.blocks, key=lambda block: min(insn_order[insn] for insn in block.insns))):
            block.origin_block_ids = {index}

        # Return and unconditional throw blocks have no normal successors;
        # additionally, blocks ending in an unconditional jump shouldn't have the next instruction as a successor
        # (if the jump target isn't the next instruction), so cut those edges
        for block in method.blocks:
            if self.is_return_insn(block.insns[-1].op) or block.insns[-1].op == 'throw':
                block.clear_successors()
            if self.is_branch_insn(block.insns[-1].op) == 'uncond':
                target_insn = method.get_insn_by_label(block.insns[-1].args[0])
                found = False
                succ = None
                for succ in block.successors:
                    if succ.insns[0] != target_insn:
                        found = True
                        succ.remove_predecessor(block)
                        break
                if found and succ:
                    block.remove_successor(succ)

        return method

    def _split_try_region_boundaries(self, method: IRMethod):
        if not method.try_regions:
            return

        boundary_labels = []
        for region in method.try_regions:
            boundary_labels.extend([
                region.try_begin,
                region.try_end,
                region.handler_begin,
                region.handler_end,
            ])

        # Keep try/catch boundaries aligned with basic-block boundaries so later
        # passes can talk about regions in terms of whole CFG blocks.
        for label in boundary_labels:
            if label is None:
                continue
            insn = method.get_insn_by_label(label)
            if insn is None:
                continue
            insn.parent_block.split_block(insn)

    @staticmethod
    def is_branch_insn(op):
        if op == 'jmp':
            return 'uncond'
        elif op in ['jeqz', 'jnez', 'jstricteqz', 'jnstricteqz', 'jeqnull', 'jnenull', 'jstricteqnull',
                      'jnsctricteqnull', 'jequndefined', 'jneundefined', 'jstrictequndefined', 'jnstrictequndefined',
                      'jeq', 'jne', 'jstricteq', 'jnstricteq']:
            return 'cond'
        else:
            return ''

    @staticmethod
    def is_return_insn(op):
        return op.startswith('return')

