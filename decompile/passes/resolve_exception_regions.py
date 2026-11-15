from decompile.ir.method import ResolvedTryRegion
from decompile.method_pass import MethodPass
from decompile.passes.buildcfg import BuildCFG


class ResolveExceptionRegions(MethodPass):
    """Map Pandasm exception entries onto CFG blocks.

    BuildCFG creates the blocks and normal edges. This pass decides which blocks
    form each protected body and handler, and rebuilds exception edges.
    """

    def run_on_method(self, method):
        method.handler_extent_unknown = False
        self._resolve_try_regions(method)
        if any(bounds.handler_block_ids is None for bounds in method.resolved_try_regions):
            # The exception entry is usable for analysis, but its body cannot be
            # safely wrapped as a source-level catch yet.
            method.handler_extent_unknown = True
        return method

    def _resolve_try_regions(self, method):
        lexical_blocks = sorted(method.blocks, key=lambda block: min(block.origin_block_ids))

        method.resolved_try_regions = []
        if not method.try_regions:
            return

        block_order = {block: index for index, block in enumerate(lexical_blocks)}

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

            # Pandasm ranges are half-open: [begin, end) and [handler, end).
            begin_index = block_order[begin_block]
            end_index = block_order[end_block]
            handler_begin_index = block_order[handler_begin_block]
            try_block_ids = set(range(begin_index, end_index))
            continuation_label = region.handler_end
            if region.handler_end is not None:
                handler_end_index = (block_order[handler_end_block]
                                     if handler_end_block is not None
                                     else len(lexical_blocks))
                handler_block_ids = set(range(handler_begin_index, handler_end_index))
            else:
                handler_block_ids, continuation_label = self._infer_simple_handler(
                    method, block_order, try_block_ids, end_block, handler_begin_block)
            if not try_block_ids:
                continue

            method.resolved_try_regions.append(ResolvedTryRegion(
                region=region,
                try_block_ids=try_block_ids,
                handler_block_ids=handler_block_ids,
                handler_entry_id=handler_begin_index,
                continuation_label=continuation_label,
            ))

        method.rebuild_exception_edges()

    def _infer_simple_handler(self, method, order, try_ids, try_end, entry):
        """Follow one path from the handler entry to find a simple catch body.

        No end label does not mean the catch is empty or runs to the method end.
        If we cannot tell where it ends, return None and leave the handler unwrapped.
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
            if BuildCFG.is_return_insn(terminator) or terminator == 'throw':
                break

            # We only follow one next block. At a branch, or a dead end without
            # return/throw, we cannot tell where the catch ends.
            if len(current.successors) != 1 or BuildCFG.is_branch_insn(terminator) == 'cond':
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

