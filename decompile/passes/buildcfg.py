from decompile.ir.method import IRMethod, ResolvedTryRegion
from decompile.method_pass import MethodPass


class BuildCFG(MethodPass):
    def run_on_method(self, method: IRMethod):
        if len(method.blocks) > 1:
            raise Exception(f'{self.__class__.__name__}: Method has more than one block, which could mean \
                a CFG has already been built. Clear it first by putting all NACs into one IRBlock.')

        insn_order = {insn: idx for idx, insn in enumerate(method.blocks[0].insns)}

        block_queue = [*method.blocks]
        while len(block_queue) > 0:
            cur_block = block_queue.pop(0)
            for i, insn in enumerate(cur_block.insns):
                branch_type = self.is_branch_insn(insn.op)
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

        # blocks ending in a return instruction shouldn't have successors;
        # additionally, blocks ending in an unconditional jump shouldn't have the next instruction as a successor
        # (if the jump target isn't the next instruction), so cut those edges
        for block in method.blocks:
            if self.is_return_insn(block.insns[-1].op):
                for succ in block.successors:
                    succ.remove_predecessor(block)
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

        self._resolve_try_regions(method, insn_order)

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
            insn = method.get_insn_by_label(label)
            if insn is None:
                continue
            insn.parent_block.split_block(insn)

    def _resolve_try_regions(self, method: IRMethod, insn_order):
        # origin_block_ids preserve lexical order through later reductions, which
        # lets try/catch packaging rebuild the region in source order afterward.
        lexical_blocks = sorted(
            method.blocks,
            key=lambda block: min(insn_order[insn] for insn in block.insns),
        )
        for idx, block in enumerate(lexical_blocks):
            block.origin_block_ids = {idx}

        method.resolved_try_regions = []
        if not method.try_regions:
            return

        block_order = {block: idx for idx, block in enumerate(lexical_blocks)}

        def label_to_block(label):
            insn = method.get_insn_by_label(label)
            return insn.parent_block if insn else None

        for region in method.try_regions:
            begin_block = label_to_block(region.try_begin)
            end_block = label_to_block(region.try_end)
            handler_begin_block = label_to_block(region.handler_begin)
            handler_end_block = label_to_block(region.handler_end)
            if None in [begin_block, end_block, handler_begin_block]:
                continue

            # Panda assembly uses half-open lexical ranges: [try_begin, try_end)
            # and [handler_begin, handler_end). Convert those label boundaries to
            # block-id ranges so later passes do not depend on CFG exception edges.
            begin_idx = block_order[begin_block]
            end_idx = block_order[end_block]
            handler_begin_idx = block_order[handler_begin_block]
            handler_end_idx = block_order[handler_end_block] if handler_end_block is not None else len(lexical_blocks)

            try_block_ids = set(range(begin_idx, end_idx))
            handler_block_ids = set(range(handler_begin_idx, handler_end_idx))
            if not try_block_ids or not handler_block_ids:
                continue

            method.resolved_try_regions.append(ResolvedTryRegion(
                region=region,
                try_block_ids=try_block_ids,
                handler_block_ids=handler_block_ids,
            ))

    def is_branch_insn(self, op):
        if op == 'jmp':
            return 'uncond'
        elif op in ['jeqz', 'jnez', 'jstricteqz', 'jnstricteqz', 'jeqnull', 'jnenull', 'jstricteqnull',
                      'jnsctricteqnull', 'jequndefined', 'jneundefined', 'jstrictequndefined', 'jnstrictequndefined',
                      'jeq', 'jne', 'jstricteq', 'jnstricteq']:
            return 'cond'
        else:
            return ''

    def is_return_insn(self, op):
        return op.startswith('return')

