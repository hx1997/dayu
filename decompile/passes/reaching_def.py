import typing

from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.exception_semantics import exception_definitions, may_throw
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType
from decompile.method_pass import MethodPass
from decompile.passes.reverse_postorder import ReversePostorder


def kill_for_instruction(insn, definitions):
    destinations = set(insn.get_defs())
    return {definition for definition in definitions if destinations.intersection(definition.get_defs())}


class ReachingDefinitions(MethodPass):
    def run_on_method(self, method: IRMethod):
        gen, kill = {}, {}
        copies = self.collect_copies(method)
        for block in method.blocks:
            gen[block], kill[block] = self.analyze_gen_kill(block, copies)
        rpo = ReversePostorder().run_on_method(method)
        return self.reaching_definitions(method, rpo, gen, kill)

    @classmethod
    def analyze_gen_kill(cls, block: IRBlock, copies, stop_on_insn=None):
        gen_block, kill_block = set(), set()
        def_block = set()

        for insn in block.insns:
            if stop_on_insn == insn:
                break
            if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL]:
                cls.analyze_assign(insn, def_block, gen_block)

        for copy_ in copies:
            copy_dst = copy_.get_defs()[0]
            for definition in def_block:
                if definition != copy_ and definition.get_defs()[0] == copy_dst:
                    # if for this copy, say x=y, x is redefined in this block, then add it to kill set
                    kill_block.add(copy_)

            # there could be nested ExprArgs on rhs, take any arguments in ExprArg into account
            for definition in def_block:
                vars_used_in_copy = []
                for arg in copy_.args[1:]:
                    if isinstance(arg, ExprArg):
                        vars_used_in_copy.extend(arg.get_used_args())
                if definition.get_defs()[0] in vars_used_in_copy:
                    kill_block.add(copy_)

        return gen_block, kill_block

    @classmethod
    def collect_copies(cls, method: IRMethod):
        copies = set()
        for block in method.blocks:
            for insn in block.insns:
                if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL]:
                    copies.add(insn)
        return copies

    @classmethod
    def analyze_assign(cls, insn, def_block, gen_block):
        def_block.add(insn)
        insn_dst = insn.get_defs()[0]

        # gen is the set of definitions (x=y) defined in this block without x or y being subsequently redefined in it
        gen_block.add(insn)

        # then, remove a previous definition from the gen set if its left-hand side is redefined
        gen_block_copy = gen_block.copy()
        for definition in gen_block_copy:
            try:
                # don't remove what we've just added
                if definition == insn:
                    continue
                def_dst = definition.get_defs()[0]
                if def_dst == insn_dst:
                    gen_block.remove(definition)
                    continue
                if def_dst.ref_obj and def_dst.ref_obj == insn_dst:
                    gen_block.remove(definition)
                    continue
                # for definitions like reg:v2 = {}, a subsequent reg:v2["abc"] = acc should cause the removal of reg:v2
                if insn_dst.ref_obj and insn_dst.ref_obj == def_dst:
                    gen_block.remove(definition)
                    continue
                # for nested ExprArg
                vars_used_in_expr = []
                for arg in definition.args[1:]:
                    if isinstance(arg, ExprArg):
                        vars_used_in_expr.extend(arg.get_used_args())
                if insn_dst in vars_used_in_expr:
                    gen_block.remove(definition)
                    continue
            except KeyError:
                pass

    def reaching_definitions(self, method: IRMethod, rpo: typing.List[IRBlock], gen, kill):
        in_block, out_block = {}, {}
        self.exception_in = {block: set() for block in method.blocks}
        self.exception_out = {block: set() for block in method.blocks}
        # add dummy entry and exit blocks
        entry_block = IRBlock()
        exit_block = IRBlock()
        entry_block.add_successor(method.blocks[0])
        no_successor_blocks = []
        for block in method.blocks:
            if self.is_no_successor_block(block):
                no_successor_blocks.append(block)
                block.add_successor(exit_block)

        extended_block_list = [entry_block, exit_block, *rpo]
        for block in extended_block_list:
            out_block[block] = set()
            self.exception_out.setdefault(block, set())
        gen[exit_block] = set()
        kill[exit_block] = set()

        out_changed = False
        first_time = True
        while out_changed or first_time:
            out_changed = False
            first_time = False
            for block in extended_block_list:
                if block != entry_block:
                    in_b = set()
                    for pred in block.predecessors:
                        in_b = in_b.union(out_block[pred])
                    # A handler may have both normal and exceptional entries.
                    # Keep definitions from both, but use the pre-throw state for
                    # every exceptional predecessor.
                    exception_b = set()
                    for pred in block.exception_predecessors:
                        exception_b.update(self.exception_in.get(pred, set()))
                    exception_b = exception_definitions(exception_b)
                    in_b.update(exception_b)
                    in_block[block] = in_b

                    old_out = out_block[block]
                    old_exception = self.exception_out[block]
                    out_block[block] = gen[block].union(in_block[block].difference(kill[block]))
                    self.exception_out[block] = self.exception_state(block, in_block[block])
                    for handler in block.exception_successors:
                        self.exception_in[handler].update(self.exception_out[block])
                    if old_out != out_block[block] or old_exception != self.exception_out[block]:
                        out_changed = True

        # remove the dummy blocks
        method.blocks[0].remove_predecessor(entry_block)
        for block in no_successor_blocks:
            block.remove_successor(exit_block)

        return in_block, out_block

    def exception_state(self, block, definitions):
        state = set(definitions)
        exception_state = set()
        for insn in block.insns:
            if may_throw(insn):
                exception_state.update(exception_definitions(state))
            state.difference_update(kill_for_instruction(insn, state))
            if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL]:
                state.add(insn)
        return exception_state

    def is_no_successor_block(self, block: IRBlock):
        return len(block.successors) == 0
