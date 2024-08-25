import collections
import random
import typing
from enum import IntEnum, auto

from decompile.ir.basicblock import IRBlock
from decompile.ir.builder import IRBuilder
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCode, NAddressCodeType
from decompile.method_pass import MethodPass
from pandasm.insn import PandasmInsnArgument


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
    def __init__(self, recover_structures=True):
        self.dominators = {}
        self.vis = set()
        self.follow_nodes: typing.Dict[IRBlock, IRBlock] = {}
        self.cur_post_order_number = 0
        self.recover_structures = recover_structures

    def run_on_method(self, method: IRMethod):
        # check that the CFG doesn't have multiple entry blocks first,
        # because the loop detection in recover_if() relies on this fact
        # encountered_entry_block = False
        # for block in method.blocks:
        #     if self.is_no_predecessor_block(block):
        #         if not encountered_entry_block:
        #             encountered_entry_block = True
        #         else:
        #             return

        _, self.dominators = self.find_dominators(method)

        # for every conditional node a, find the set of nodes immediately dominated by a
        imm_dominated_by_cond_node = self.find_imm_dominated_by_cond_node(method)
        # let G' be the graph produced by reversing all the arrows in the CFG G. Filter out nodes from the set above
        # that do not dominate a in G'
        _, reversed_dominators = self.find_dominators(method, True)
        dominators_in_reversed = {}
        for cond_node, imm_dominated in imm_dominated_by_cond_node.items():
            cond_node_dominators_in_reversed = reversed_dominators[cond_node]
            for node in imm_dominated.copy():
                if node not in cond_node_dominators_in_reversed:
                    imm_dominated.remove(node)
            dominators_in_reversed[cond_node] = imm_dominated

        # dominators_in_reversed maps each conditional node to the set of nodes immediately dominated by it in G and
        # dominating it in the reversed graph G'
        # for each set of nodes, there exists a unique follow node which is the highest-numbered (i.e. last visited)
        # node in a post-order traversal of the graph G
        post_order_numbering = self.get_post_order_numbering(method)
        self.follow_nodes = {}
        for cond_node, candidate_follow_nodes in dominators_in_reversed.items():
            max_num = -1
            follow_node = None
            cond_node_order = post_order_numbering[cond_node]
            for candidate_follow_node in candidate_follow_nodes:
                if post_order_numbering[candidate_follow_node] > max_num:
                    max_num = post_order_numbering[candidate_follow_node]
                    follow_node = candidate_follow_node
            self.follow_nodes[cond_node] = (follow_node, cond_node_order)  # keep track of the order and follow this order in recover_if

        for block in method.blocks:
            self.insert_jump_at_block_end(block)

        if self.recover_structures:
            self.recover_if()
        pass

    def insert_jump_at_block_end(self, block: IRBlock):
        if block.insns[-1].type not in [NAddressCodeType.UNCOND_JUMP, NAddressCodeType.COND_JUMP, NAddressCodeType.RETURN]:
            if len(block.successors) == 1:
                builder = IRBuilder(block.parent_method.parent_class.parent_module)
                builder.set_insert_point(block)
                target_label = block.successors[0].insns[0].label
                target = PandasmInsnArgument('label', target_label)
                builder.create_uncond_jump(target)
            else:
                raise Exception(f'[{self.__class__.__name__}] error: non-jumping block has more than one successor')

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

    def get_immediate_dominatee(self, block: IRBlock):
        imm_dominatees = set()
        for other_block in block.parent_method.blocks:
            if block != other_block and block in self.dominators[other_block]:
                # block strictly dominates some other block (other_block)
                other_block_strict_dominators = self.dominators[other_block].difference({other_block})
                if len(other_block_strict_dominators) == 0:
                    imm_dominatees.add(other_block)
                    continue

                is_imm_dominatee = True
                for other_dom in other_block_strict_dominators:
                    # ensure block does not strictly dominate any block that strictly dominates other_block
                    # other_dom is "any block that strictly dominates other_block", check that block does not strictly
                    # dominate it
                    if block in self.dominators[other_dom] and block != other_dom:
                        is_imm_dominatee = False
                        break
                if is_imm_dominatee:
                    imm_dominatees.add(other_block)
        return imm_dominatees

    def find_imm_dominated_by_cond_node(self, method: IRMethod):
        imm_dominated_by_cond_node = {}
        for block in method.blocks:
            if len(block.successors) != 2:
                # not a conditional node
                continue
            imm_dom = self.get_immediate_dominatee(block)
            imm_dominated_by_cond_node[block] = imm_dom
        return imm_dominated_by_cond_node

    def get_post_order_numbering(self, method: IRMethod):
        self.vis.clear()
        self.cur_post_order_number = 0
        post_order_numbering = {}
        for block in method.blocks:
            if block not in self.vis:
                self._do_get_post_order_numbering(block, post_order_numbering)
        return post_order_numbering

    def _do_get_post_order_numbering(self, block: IRBlock, post_order_numbering_dict: dict):
        if block in self.vis:
            return

        self.vis.add(block)
        for succ in block.successors:
            self._do_get_post_order_numbering(succ, post_order_numbering_dict)

        post_order_numbering_dict[block] = self.cur_post_order_number
        self.cur_post_order_number += 1

    def recover_if(self):
        # traverse the conditional nodes in post order to ensure inner nested ifs are processed before outer ones
        ordered_cond_node = {}
        for cond_node, (follow_node, node_order) in self.follow_nodes.items():
            ordered_cond_node[node_order] = (cond_node, follow_node)
        ordered_cond_node = collections.OrderedDict(sorted(ordered_cond_node.items()))

        for cond_node, follow_node in ordered_cond_node.values():
            if follow_node is None:
                # stop recovering if no follow node found for this conditional node
                # because in this case we can't recover this conditional, which can lead to wrong recovery
                # if this conditional is structurally enclosed by subsequent conditional nodes (i.e. nested if)
                break
            is_loop = False
            for pred in cond_node.predecessors:
                if self.is_back_edge(pred, cond_node):
                    # presence of a back edge means this is a loop, not a branch
                    # doesn't work if the CFG has multiple entry blocks (this was checked at the start of run_on_method)
                    # TODO: does this cover do-whiles?
                    is_loop = True
                    break
            if is_loop:
                continue

            # check which type of if we have here
            follow_node_in_children = follow_node in cond_node.successors
            if follow_node_in_children:
                self.recover_if_type1_2(cond_node, follow_node)
            else:
                # type 3: if-else-then
                self.recover_if_type3(cond_node, follow_node)

    def recover_if_type1_2(self, cond_node, follow_node):
        cond_jump_insn = cond_node.insns[-1]
        cond_jump_target = cond_node.parent_method.get_insn_by_label(cond_jump_insn.args[2].value).parent_block
        if cond_jump_target == follow_node:
            # type 1: if (!condition) { [non follow node] } [follow node]
            # negate the condition if it's type 1
            if not cond_jump_insn.reverse_relational_operation():
                return
        else:
            # type 2: if (condition) { [non follow node] } [follow node]
            # do nothing here if it's type 2
            pass

        # now, something to do for both type 1 and 2
        new_if_text = f'if ({cond_jump_insn.args[0]} {cond_jump_insn.op} {cond_jump_insn.args[1]})' + ' {'
        new_if = NAddressCode(new_if_text, [], nac_type=NAddressCodeType.UNKNOWN, label_name=cond_jump_insn.label)
        cond_jump_insn.erase_from_parent()
        cond_node.insert_insn(new_if)

        non_follow_node = [node for node in cond_node.successors if node != follow_node][0]
        for insn in non_follow_node.insns:
            cond_node.insert_insn(insn)

        cond_node.insert_insn(NAddressCode('}', [], nac_type=NAddressCodeType.UNKNOWN))

        cond_node.clear_successors()
        cond_node.add_successor(follow_node)
        non_follow_node.erase_from_parent()

    def recover_if_type3(self, cond_node, follow_node):
        cond_jump_insn = cond_node.insns[-1]
        cond_jump_target = cond_node.parent_method.get_insn_by_label(cond_jump_insn.args[2].value).parent_block
        non_cond_jump_target = [node for node in cond_node.successors if node != cond_jump_target][0]

        new_if_text = f'if ({cond_jump_insn.args[0]} {cond_jump_insn.op} {cond_jump_insn.args[1]})' + ' {'
        new_if = NAddressCode(new_if_text, [], nac_type=NAddressCodeType.UNKNOWN, label_name=cond_jump_insn.label)
        cond_jump_insn.erase_from_parent()
        cond_node.insert_insn(new_if)

        for insn in cond_jump_target.insns:
            cond_node.insert_insn(insn)

        cond_node.insert_insn(NAddressCode('} else {', [], nac_type=NAddressCodeType.UNKNOWN))

        for insn in non_cond_jump_target.insns:
            cond_node.insert_insn(insn)

        cond_node.insert_insn(NAddressCode('}', [], nac_type=NAddressCodeType.UNKNOWN))
        cond_node.clear_successors()
        cond_node.add_successor(follow_node)
        cond_jump_target.erase_from_parent()
        non_cond_jump_target.erase_from_parent()

    def is_back_edge(self, block_src: IRBlock, block_dst: IRBlock):
        return block_dst in self.dominators[block_src]
