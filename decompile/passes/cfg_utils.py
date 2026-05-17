from decompile.ir.method import IRMethod


class CFGUtils:
    @staticmethod
    def crosses_resolved_try_region_boundary(origin_ids, method: IRMethod):
        # Ordinary control-flow reductions must stay inside either the try body,
        # the handler body, or outside the region entirely.
        if not method.resolved_try_regions:
            return False

        for bounds in method.resolved_try_regions:
            try_ids = bounds.try_block_ids
            handler_ids = bounds.handler_block_ids
            in_try = bool(origin_ids.intersection(try_ids))
            in_handler = bool(origin_ids.intersection(handler_ids))
            in_region = in_try or in_handler
            outside_region = bool(origin_ids.difference(try_ids.union(handler_ids)))
            if (in_try and in_handler) or (in_region and outside_region):
                return True
        return False

    @staticmethod
    def find_dominators(method: IRMethod, reverse_graph=False):
        in_d, out_d = {}, {}
        entry_blocks = set()
        for block in method.blocks:
            if ((not reverse_graph and CFGUtils.is_no_predecessor_block(block))
                    or (reverse_graph and CFGUtils.is_no_successor_block(block))):
                out_d[block] = {block}
                entry_blocks.add(block)

        for block in method.blocks:
            if block not in entry_blocks:
                out_d[block] = set(method.blocks)

        out_changed = False
        first_time = True
        while out_changed or first_time:
            out_changed = False
            first_time = False
            for block in method.blocks:
                if block in entry_blocks:
                    continue
                pred_or_succ = block.successors if reverse_graph else block.predecessors
                if pred_or_succ:
                    out_p = out_d[pred_or_succ[0]]
                    for pred in pred_or_succ[1:]:
                        out_p = out_p.intersection(out_d[pred])
                else:
                    out_p = set()
                in_d[block] = out_p

                old_out_d = out_d.copy()
                out_d[block] = in_d[block].union({block})
                if old_out_d != out_d:
                    out_changed = True

        return in_d, out_d

    @staticmethod
    def is_no_predecessor_block(block):
        return len(block.predecessors) == 0

    @staticmethod
    def is_no_successor_block(block):
        return len(block.successors) == 0