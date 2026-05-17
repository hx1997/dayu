from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType, UnknownNAC
from decompile.method_pass import MethodPass


class ProcessTryCatchRegions(MethodPass):
    def run_on_method(self, method: IRMethod):
        if not method.resolved_try_regions:
            return

        # These labels delimit synthetic structure only. They may be stripped once
        # we know no remaining jump still targets them.
        self.structural_labels = set()
        for bounds in method.resolved_try_regions:
            self.structural_labels.update({
                bounds.region.try_begin,
                bounds.region.try_end,
                bounds.region.handler_begin,
                bounds.region.handler_end,
            })

        self.wrap_try_catch_regions(method)
        self.strip_structural_labels(method)
        self.reorder_blocks_lexically(method)

    def wrap_try_catch_regions(self, method: IRMethod):
        def sort_key(bounds):
            all_ids = bounds.try_block_ids.union(bounds.handler_block_ids)
            return (len(all_ids), -min(all_ids))

        # Wrap inner regions first so nested try/catch has already collapsed into
        # a single node before the outer region is assembled.
        for bounds in sorted(method.resolved_try_regions, key=sort_key):
            try_nodes = [block for block in method.blocks if block.origin_block_ids.intersection(bounds.try_block_ids)]
            handler_nodes = [block for block in method.blocks if block.origin_block_ids.intersection(bounds.handler_block_ids)]
            if not try_nodes or not handler_nodes:
                continue

            try_nodes = self.sort_nodes_lexically(try_nodes)
            handler_nodes = self.sort_nodes_lexically(handler_nodes)

            try_set = set(try_nodes)
            handler_set = set(handler_nodes)
            if try_set.intersection(handler_set):
                continue

            node = self.create_try_catch_node(bounds.region, try_nodes, handler_nodes)
            node.origin_block_ids = self.union_origin_block_ids(try_nodes + handler_nodes)
            self.replace_region_nodes(method, node, try_nodes + handler_nodes)

    def sort_nodes_lexically(self, nodes):
        return sorted(nodes, key=lambda node: min(node.origin_block_ids) if node.origin_block_ids else -1)

    def union_origin_block_ids(self, blocks):
        origin_ids = set()
        for block in blocks:
            origin_ids.update(block.origin_block_ids)
        return origin_ids

    def create_try_catch_node(self, region, try_nodes, handler_nodes):
        node = IRBlock(parent_method=None)
        node.insert_insn(UnknownNAC('try {', []))
        structural_labels = {region.try_begin, region.try_end, region.handler_begin, region.handler_end}

        for block in try_nodes:
            for insn in block.insns:
                # Jumps that only skip from try_end to handler_end are structural
                # artifacts; once we emit a textual try/catch wrapper they should disappear.
                if (insn.type is NAddressCodeType.UNCOND_JUMP and
                        insn.target.value in self.structural_labels):
                    continue
                if insn.label in structural_labels:
                    insn.label = ''
                node.insert_insn(insn)

        node.insert_insn(UnknownNAC('} catch {', []))

        for block in handler_nodes:
            for insn in block.insns:
                if insn.label in structural_labels:
                    insn.label = ''
                node.insert_insn(insn)

        node.insert_insn(UnknownNAC('}', []))
        return node

    def replace_region_nodes(self, method: IRMethod, node: IRBlock, region_nodes):
        region_node_set = set(region_nodes)
        insert_pos = min(method.blocks.index(block) for block in region_nodes)
        method.blocks.insert(insert_pos, node)
        node.parent_method = method

        # Rewire all external predecessors/successors through the new synthetic
        # try/catch node, then drop the old region blocks from the method.
        for block in list(method.blocks):
            if block == node or block in region_node_set:
                continue
            succ_inside_region = region_node_set.intersection(set(block.successors))
            for succ in succ_inside_region:
                block.remove_successor(succ)
                block.add_successor(node)
                for succ_succ in succ.successors:
                    if succ_succ not in region_node_set:
                        node.add_successor(succ_succ)

            pred_inside_region = region_node_set.intersection(set(block.predecessors))
            for pred in pred_inside_region:
                block.remove_predecessor(pred)
                block.add_predecessor(node)
                for pred_pred in pred.predecessors:
                    if pred_pred not in region_node_set:
                        node.add_predecessor(pred_pred)

        for block in region_nodes:
            block.clear_successors()
            block.clear_predecessors()
            if block in method.blocks:
                method.blocks.remove(block)

    def strip_structural_labels(self, method: IRMethod):
        referenced_labels = set()
        for block in method.blocks:
            for insn in block.insns:
                if insn.type in [NAddressCodeType.UNCOND_JUMP, NAddressCodeType.COND_JUMP]:
                    referenced_labels.add(insn.target.value)

        for block in method.blocks:
            for insn in block.insns:
                if insn.label in self.structural_labels and insn.label not in referenced_labels:
                    insn.label = ''

    def reorder_blocks_lexically(self, method: IRMethod):
        # Reductions can disturb block list order; restore lexical order so the
        # final pseudocode stays close to the original instruction layout.
        method.blocks.sort(key=lambda block: min(block.origin_block_ids) if block.origin_block_ids else -1)