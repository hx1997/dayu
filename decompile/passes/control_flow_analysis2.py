from decompile.ir.method import IRMethod
from decompile.method_pass import MethodPass


class ControlFlowAnalysis2(MethodPass):
    """
    buggy, don't use
    """
    def __init__(self):
        self.struct_of = {}
        self.struct_type = {}
        self.structures = set()
        self.struct_nodes = {}
        self.ct_nodes = set()
        self.ct_edges = set()
        self.post_ctr = 0
        self.post_max = 0
        self.post = {}
        self.visit = {}

    def run_on_method(self, method: IRMethod):
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
                    if self.is_back_edge(k, succ):
                        return True
        return False

    def structural_analysis(self, method: IRMethod):
        entry = method.blocks[0]
        self.ct_nodes = set(method.blocks)
        node_set = set()
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
                rtype = self.acyclic_region_type(method, n, node_set)
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
                    rtype = self.cyclic_region_type(method, n, reach_under)
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

    def acyclic_region_type(self, method: IRMethod, node, nset: set):
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

    def cyclic_region_type(self, method: IRMethod, node, nset):
        if len(nset) == 1:
            if node in node.successors:
                return RegionType.SelfLoop
            else:
                return None

        # FIXME: handle Improper regions

        m = random.choice(nset.difference({node}))
        if len(node.successors) == 2 and len(m.predecessors) == 1 and len(node.predecessors) == 2 and len(m.successors) == 1:
            return RegionType.WhileLoop
        else:
            return RegionType.NaturalLoop

    def reduce(self, method: IRMethod, rtype, node_set):
        node = IRBlock(parent_method=method)
        self.replace(method, node, node_set)
        self.struct_type[node] = rtype
        self.structures = self.structures.union({node})
        for m in node_set:
            self.struct_of[m] = node
        self.struct_nodes[node] = node_set
        return node

    def replace(self, method: IRMethod, node, node_set):
        self.compact(node, node_set)
        _, self.dominators = self.find_dominators(method)
        for block in method.blocks:
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

    def compact(self, node, node_set):
        max_num = -1
        for i in range(1, self.post_max):
            if self.post[i] in node_set and i > max_num:
                max_num = i
                del self.post[i]
        self.post[max_num] = node
        # for n in node_set:
        #     n.clear_successors()
        #     n.clear_predecessors()
        #     n.erase_from_parent()
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
