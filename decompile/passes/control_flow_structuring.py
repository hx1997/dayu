import random

from ordered_set import OrderedSet

from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCode, NAddressCodeType
from decompile.method_pass import MethodPass
from enum import IntEnum, auto

class RegionType(IntEnum):
    Block = auto()
    IfThen = auto()
    IfThenElse = auto()
    Case = auto()
    Proper = auto()
    SelfLoop = auto()
    WhileLoop = auto()
    NaturalLoop = auto()
    Improper = auto()


class ControlFlowStructuring(MethodPass):
    """
    Note: This pass doesn't maintain the CFG. It's meant to be used in final stages of decompilation
    to recover high-level control structures like "if" or "while". Having reached these stages,
    we're going to produce the final pseudocode so IR constraints and CFG don't matter anymore
    """
    def __init__(self):
        self.struct_of = {}
        self.struct_type = {}
        self.structures = OrderedSet()
        self.struct_nodes = {}
        self.ct_nodes = OrderedSet()
        self.ct_edges = OrderedSet()
        self.post_ctr = 0
        self.post_max = 0
        self.post = {}
        self.visit = {}
        self.dominators = {}

    def run_on_method(self, method: IRMethod):
        _, self.dominators = self.find_dominators(method)
        self.structural_analysis(method)

    def reaches(self, block_src: IRBlock, block_dst: IRBlock, avoid=None):
        if not avoid:
            avoid = []
        vis = set()
        return self._do_reaches(block_src, block_dst, vis, avoid)

    def _do_reaches(self, block_src: IRBlock, block_dst: IRBlock, vis, avoid):
        if block_src in vis or block_src in avoid:
            return False
        if block_src == block_dst:
            return True

        vis.add(block_src)
        for succ in block_src.successors:
            if self._do_reaches(succ, block_dst, vis, avoid):
                return True
        return False

    def path_back(self, method: IRMethod, m: IRBlock, n: IRBlock):
        for k in method.blocks:
            if k == m or self.reaches(m, k, [n]):
                for succ in k.successors:
                    if succ == n and self.is_back_edge(k, succ):
                        return True
        return False

    def is_back_edge(self, block_src: IRBlock, block_dst: IRBlock):
        return block_dst in self.dominators[block_src]

    def find_dominators(self, method: IRMethod, reverse_graph=False):
        in_d, out_d = {}, {}
        entry_blocks = set()
        for block in method.blocks:
            if (not reverse_graph and self.is_no_predecessor_block(block)) or (reverse_graph and self.is_no_successor_block(block)):
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
                if reverse_graph:
                    pred_or_succ = block.successors
                else:
                    pred_or_succ = block.predecessors
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

    def is_no_predecessor_block(self, block: IRBlock):
        return len(block.predecessors) == 0

    def is_no_successor_block(self, block: IRBlock):
        return len(block.successors) == 0

    def structural_analysis(self, method: IRMethod):
        entry = method.blocks[0]
        self.ct_nodes = OrderedSet(method.blocks)
        node_set = OrderedSet()
        is_first = True
        identified = False
        while is_first or identified:
            is_first = False
            identified = False
            self.post_max = 0
            self.post_ctr = 1
            self.dfs_postorder(method, entry)
            while len(method.blocks) > 1 and self.post_ctr <= self.post_max:
                n = self.post[self.post_ctr]
                rtype = self.acyclic_region_type(n, node_set)
                if rtype is not None:
                    identified = True
                    p = self.reduce(method, rtype, node_set)
                    if entry in node_set:
                        entry = p
                else:
                    reach_under = {n}
                    for m in method.blocks:
                        if self.path_back(method, m, n):
                            reach_under = reach_under.union({m})
                    rtype = self.cyclic_region_type(n, reach_under)
                    if rtype is not None and rtype not in [RegionType.NaturalLoop]:
                        identified = True
                        p = self.reduce(method, rtype, reach_under)
                        if entry in reach_under:
                            entry = p
                    else:
                        self.post_ctr += 1

    def dfs_postorder(self, method: IRMethod, x):
        self.visit[x] = True
        for y in x.successors:
            if y not in self.visit:
                self.dfs_postorder(method, y)
        self.post_max += 1
        self.post[self.post_max] = x

    def acyclic_region_type(self, node, nset: OrderedSet):
        nset.clear()
        n = node
        p = True
        s = len(n.successors) == 1
        while p and s:
            nset_union = nset.union({n})
            nset.clear()
            nset.update(nset_union)
            n = random.choice(list(n.successors))
            p = len(n.predecessors) == 1
            s = len(n.successors) == 1
        if p:
            nset_union = nset.union({n})
            nset.clear()
            nset.update(nset_union)
        n = node
        p = len(n.predecessors) == 1
        s = True
        while p and s:
            nset_union = nset.union({n})
            nset.clear()
            nset.update(nset_union)
            n = random.choice(list(n.predecessors))
            p = len(n.predecessors) == 1
            s = len(n.successors) == 1
        if s:
            nset_union = nset.union({n})
            nset.clear()
            nset.update(nset_union)
        node = n
        if len(nset) >= 2:
            return RegionType.Block
        elif len(node.successors) == 2:
            m = [_node for _node in node.successors if len(_node.predecessors) == 1][0]
            n = [_node for _node in node.successors if _node != m][0]
            if m.successors == n.successors and len(m.successors) == 1 and len(m.predecessors) == 1 and len(n.predecessors) == 1:
                nset.clear()
                nset.update({node, m, n})
                return RegionType.IfThenElse
            elif len(m.successors) == 1 and m.successors[0] == n and len(n.predecessors) == 2:
                nset.clear()
                nset.update({node, m})
                return RegionType.IfThen
            else:
                return None

    def cyclic_region_type(self, node, nset):
        if len(nset) == 1:
            if node in node.successors:
                return RegionType.SelfLoop
            else:
                return None

        # FIXME: handle Improper regions

        m = random.choice(list(nset.difference({node})))
        if len(node.successors) == 2 and len(m.predecessors) == 1 and len(node.predecessors) == 2 and len(m.successors) == 1:
            return RegionType.WhileLoop
        else:
            return RegionType.NaturalLoop

    def reduce(self, method: IRMethod, rtype, node_set):
        node = self.create_node_with_rtype(method, node_set, rtype)
        self.replace(method, node, node_set)
        self.struct_type[node] = rtype
        self.structures = self.structures.union({node})
        for m in node_set:
            self.struct_of[m] = node
        self.struct_nodes[node] = node_set

        if rtype is RegionType.SelfLoop:
            node.remove_successor(node)
        return node

    def create_node_with_rtype(self, parent_method: IRMethod, node_set, rtype):
        if rtype is RegionType.WhileLoop:
            # identify the loop header block
            loop_header = None
            for node in node_set:
                for succ in node.successors:
                    if succ in self.dominators[node] and self.is_back_edge(node, succ):
                        loop_header = succ

            if loop_header is None:
                raise Exception()

            node = IRBlock(parent_method=parent_method)

            # copy every instruction (except the last one which is a jump) of the header into the new block
            for insn in loop_header.insns[:-1]:
                node.insert_insn(insn)

            cond_jump_insn = loop_header.insns[-1]
            cond_jump_insn_label = cond_jump_insn.label
            # invert the jump condition, because it's the condition for exiting the loop, whereas we want
            # the condition for entering the loop
            cond_jump_insn.invert_relational_operation()

            new_while_text = f'while ({cond_jump_insn.args[0]} {cond_jump_insn.op} {cond_jump_insn.args[1]})' + ' {'
            new_while = NAddressCode(new_while_text, [], nac_type=NAddressCodeType.UNKNOWN, label_name=cond_jump_insn.label)
            cond_jump_insn.erase_from_parent()
            node.insert_insn(new_while)

            for insn in loop_header.insns:
                node.insert_insn(insn)

            cur_block = loop_header
            vis = set()
            while not vis.issuperset(node_set):
                for succ in cur_block.successors:
                    if succ not in node_set:
                        continue
                    if succ == loop_header:
                        vis.add(succ)
                        continue
                    if len(succ.successors) > 1:
                        raise Exception()

                    for insn in succ.insns:
                        # don't insert the jump back to loop header
                        if insn.type is NAddressCodeType.UNCOND_JUMP:
                            if insn.args[0].value == cond_jump_insn_label:
                                continue
                        node.insert_insn(insn)

                    vis.add(succ)
                cur_block = cur_block.successors[0]

            node.insert_insn(NAddressCode('}', [], nac_type=NAddressCodeType.UNKNOWN))
            return node
        elif rtype is RegionType.Block:
            # find region entry block
            entry = None
            for node in node_set:
                if len(node.predecessors) == 0:
                    entry = node
                    break
                for pred in node.predecessors:
                    if pred not in node_set:
                        entry = node

            if entry is None:
                raise Exception()

            node = IRBlock(parent_method=parent_method)

            q = [entry]
            vis = set()
            while len(q) != 0:
                old_node = q.pop()
                if old_node not in node_set:
                    continue

                if len(old_node.successors) <= 1:
                    # for Block type regions, the last block may have more than one successor
                    # don't add those successors to the queue as they are not part of the region
                    for succ in old_node.successors:
                        q.append(succ)

                for insn in old_node.insns:
                    node.insert_insn(insn)

                vis.add(old_node)

            return node
        elif rtype is RegionType.SelfLoop:
            node = IRBlock(parent_method=parent_method)

            first_node = list(node_set)[0]
            new_while_text = 'do {'
            new_while = NAddressCode(new_while_text, [], nac_type=NAddressCodeType.UNKNOWN, label_name=first_node.insns[0].label)
            node.insert_insn(new_while)

            for old_node in node_set:
                for insn in old_node.insns:
                    node.insert_insn(insn)

            node.insert_insn(NAddressCode('} while (true);', [], nac_type=NAddressCodeType.UNKNOWN))
            return node
        elif rtype is RegionType.IfThen:
            # find the conditional node
            cond_node = None
            then_node = None
            for node in node_set:
                if len(node.successors) == 2:
                    cond_node = node
                    if parent_method.get_insn_by_label(node.insns[-1].args[-1].value).parent_block == node.successors[0]:
                        then_node = node.successors[1]
                    else:
                        then_node = node.successors[0]

            if cond_node is None:
                raise Exception()

            node = IRBlock(parent_method=parent_method)

            # copy every instruction (except the last one which is a jump) of the header into the new block
            for insn in cond_node.insns[:-1]:
                node.insert_insn(insn)

            cond_jump_insn = cond_node.insns[-1]
            cond_jump_insn_label = cond_jump_insn.label
            # invert the jump condition, because it's the condition for exiting the branch, whereas we want
            # the condition for entering the branch
            cond_jump_insn.invert_relational_operation()

            new_if_text = f'if ({cond_jump_insn.args[0]} {cond_jump_insn.op} {cond_jump_insn.args[1]})' + ' {'
            new_if = NAddressCode(new_if_text, [], nac_type=NAddressCodeType.UNKNOWN, label_name=cond_jump_insn.label)
            cond_jump_insn.erase_from_parent()
            node.insert_insn(new_if)

            for insn in then_node.insns:
                # don't insert the jump out of the branch
                if insn.type is NAddressCodeType.UNCOND_JUMP:
                    if insn.args[0].value == cond_jump_insn_label:
                        continue
                node.insert_insn(insn)

            node.insert_insn(NAddressCode('}', [], nac_type=NAddressCodeType.UNKNOWN))
            return node
        elif rtype is RegionType.IfThenElse:
            # find the conditional node
            cond_node = None
            then_node, else_node = None, None
            for node in node_set:
                if len(node.successors) == 2:
                    cond_node = node
                    if parent_method.get_insn_by_label(node.insns[-1].args[-1].value).parent_block == node.successors[0]:
                        then_node = node.successors[1]
                        else_node = node.successors[0]
                    else:
                        then_node = node.successors[0]
                        else_node = node.successors[1]

            if cond_node is None:
                raise Exception()

            node = IRBlock(parent_method=parent_method)

            # copy every instruction (except the last one which is a jump) of the header into the new block
            for insn in cond_node.insns[:-1]:
                node.insert_insn(insn)

            cond_jump_insn = cond_node.insns[-1]
            # invert the jump condition, because it's the condition for the else branch, whereas we want
            # the condition for the then branch
            cond_jump_insn.invert_relational_operation()

            new_if_text = f'if ({cond_jump_insn.args[0]} {cond_jump_insn.op} {cond_jump_insn.args[1]})' + ' {'
            new_if = NAddressCode(new_if_text, [], nac_type=NAddressCodeType.UNKNOWN, label_name=cond_jump_insn.label)
            cond_jump_insn.erase_from_parent()
            node.insert_insn(new_if)

            for idx, insn in enumerate(then_node.insns):
                # don't insert the jump out of the branch
                if insn.type is NAddressCodeType.UNCOND_JUMP and idx == len(then_node.insns)-1:
                    continue
                node.insert_insn(insn)

            node.insert_insn(NAddressCode('} else {', [], nac_type=NAddressCodeType.UNKNOWN))

            for idx, insn in enumerate(else_node.insns):
                # don't insert the jump out of the branch
                if insn.type is NAddressCodeType.UNCOND_JUMP and idx == len(then_node.insns)-1:
                    continue
                node.insert_insn(insn)

            node.insert_insn(NAddressCode('}', [], nac_type=NAddressCodeType.UNKNOWN))
            return node
        else:
            return IRBlock(parent_method=parent_method)


    def replace(self, method: IRMethod, node, node_set):
        self.compact(node, node_set)
        _, self.dominators = self.find_dominators(method)
        for block in method.blocks:
            if block == node:
                continue
            if block in node_set:
                continue
            succ_inside_region = node_set.intersection(set(block.successors))
            for succ in succ_inside_region:
                block.remove_successor(succ)
                if block != node:
                    block.add_successor(node)
                for succ_succ in succ.successors:
                    if succ_succ not in node_set:
                        node.add_successor(succ_succ)
            pred_inside_region = node_set.intersection(set(block.predecessors))
            for pred in pred_inside_region:
                block.remove_predecessor(pred)
                if block != node:
                    block.add_predecessor(node)
                for pred_pred in pred.predecessors:
                    if pred_pred not in node_set:
                        node.add_predecessor(pred_pred)

        for n in node_set:
            n.clear_successors()
            n.clear_predecessors()
            n.erase_from_parent()

    def compact(self, node, node_set):
        max_num = -1
        for i in range(1, self.post_max):
            if self.post[i] in node_set and i > max_num:
                max_num = i
                del self.post[i]
        self.post[max_num] = node
        post_sorted = sorted(self.post)
        cur_pos = 1
        new_post = {}
        for n in post_sorted:
            new_post[cur_pos] = self.post[n]
            if self.post[n] == node:
                self.post_ctr = cur_pos
            cur_pos += 1
        self.post = new_post
        self.post_max = len(self.post)
