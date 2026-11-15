from decompile.ir.method import IRMethod, ResolvedTryRegion
from decompile.method_pass import MethodPass


class BuildCFG(MethodPass):
    def run_on_method(self, method: IRMethod):
        if len(method.blocks) > 1:
            raise Exception(f'{self.__class__.__name__}: Method has more than one block, which could mean \
                a CFG has already been built. Clear it first by putting all NACs into one IRBlock.')

        original_insns = list(method.blocks[0].insns)
        insn_order = {insn: idx for idx, insn in enumerate(original_insns)}

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

        self._resolve_try_regions(method, insn_order)
        if any(bounds.handler_block_ids is None for bounds in method.resolved_try_regions):
            method.low_level_exception_fallback = True
            # Keep the original instruction order and exception metadata intact.
            method.exception_fallback_lines = [
                '// Handler extent is unknown; emitting low-level control flow.',
                *method.raw_listing,
                *[f'.catchall {r.try_begin}, {r.try_end}, {r.handler_begin}'
                  + (f', {r.handler_end}' if r.handler_end is not None else '')
                  for r in method.try_regions],
            ]

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
            insn = method.get_insn_by_label(label) if label is not None else None
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
            try_block_ids = set(range(begin_idx, end_idx))
            continuation_label = region.handler_end
            if region.handler_end is not None:
                handler_end_idx = block_order[handler_end_block] if handler_end_block is not None else len(lexical_blocks)
                handler_block_ids = set(range(handler_begin_idx, handler_end_idx))
            else:
                handler_block_ids, continuation_label = self._infer_simple_handler(
                    method, block_order, try_block_ids,
                    end_block, handler_begin_block)
            if not try_block_ids:
                continue

            method.resolved_try_regions.append(ResolvedTryRegion(
                region=region,
                try_block_ids=try_block_ids,
                handler_block_ids=handler_block_ids,
                handler_entry_id=handler_begin_idx,
                continuation_label=continuation_label,
            ))

        method.rebuild_exception_edges()

    def _infer_simple_handler(self, method, order, try_ids, try_end, entry):
        """Follow one path from the handler entry to find a simple catch body.

        No end label does not mean the catch is empty or runs to the method end.
        If we cannot tell where it ends, return None and keep the raw code.
        """
        # With several handlers, catches may be nested or share code.
        # Walking just one of them cannot tell which code belongs to which catch.
        if len(method.try_regions) != 1:
            return None, None

        # Async and finally also use catchall, but are not ordinary catch bodies.
        # This simple walk does not know how to turn them back into source code.
        if any(insn.op.startswith(('async', 'suspend', 'resume', 'ldhole'))
               for block in method.blocks for insn in block.insns):
            return None, None

        # After a successful try, this jump skips the catch.
        # Its target may be the code after catch; check the catch path below.
        candidate = None
        if try_end is not entry and len(try_end.insns) == 1 and try_end.insns[0].op == 'jmp':
            candidate_insn = method.get_insn_by_label(try_end.insns[0].args[0])
            candidate = candidate_insn.parent_block if candidate_insn else None
        path = []
        current = entry
        while current is not candidate:
            # Stop if we loop back or enter the try again. This walk only handles
            # a catch that goes forward along one path.
            if current in path or order[current] in try_ids:
                return None, None

            # Another normal path enters this block, so putting it inside catch
            # could also pull in code that should run after try/catch.
            if any(pred not in path for pred in current.predecessors):
                return None, None

            path.append(current)
            terminator = current.insns[-1].op
            # return/throw ends this path, so there is no need to find a join.
            if self.is_return_insn(terminator) or terminator == 'throw':
                break

            # We only follow one next block. At a branch, or a dead end without
            # return/throw, we cannot tell where the catch ends.
            if len(current.successors) != 1 or self.is_branch_insn(terminator) == 'cond':
                return None, None
            current = current.successors[0]
        # The handler starts where normal execution continues. This might be an
        # empty catch, but this walk cannot yet rule out shared cleanup code.
        if not path:
            return None, None

        ids = {order[block] for block in path}
        # The printer keeps the original block order. Only accept consecutive
        # blocks visited in that order, or it would print a different path.
        if [order[block] for block in path] != list(range(min(ids), max(ids) + 1)):
            return None, None

        continuation = None
        if candidate is not None:
            # We print the code after try/catch last, so its target must come
            # after every catch block in the original instruction order.
            if candidate in path or order[candidate] <= max(ids):
                return None, None

            continuation = str(try_end.insns[0].args[0])
            # Include the jump that skips catch in the try body. When we print
            # try/catch, normal execution already skips catch, so we remove it.
            try_ids.add(order[try_end])
        return ids, continuation

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

