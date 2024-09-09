import typing

from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType, NAddressCode
from decompile.method_pass import MethodPass
from decompile.passes.reverse_postorder import ReversePostorder
from pandasm.insn import PandasmInsnArgument


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
            for definition in def_block:
                if definition != copy_ and definition.args[0] == copy_.args[0]:
                    # if for this copy, say x=y, x is redefined in this block, then add it to kill set
                    kill_block.add(copy_)

            # there could be nested ExprArgs on rhs, take any arguments in ExprArg into account
            for definition in def_block:
                vars_used_in_copy = []
                for arg in copy_.args[1:]:
                    if isinstance(arg, ExprArg):
                        vars_used_in_copy.extend(arg.get_used_args())
                if definition.args[0] in vars_used_in_copy:
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
    def analyze_assign(cls, insn: NAddressCode, def_block, gen_block):
        def_block.add(insn)

        # gen is the set of definitions (x=y) defined in this block without x or y being subsequently redefined in it
        # first add to the set this assign instruction
        if len(insn.args) == 2:
            gen_block.add(insn)
        elif len(insn.args) >= 3:
            # for the three-argument ASSIGN case x=y+z and the CALL case x = y(z1,z2,...)
            gen_block.add(insn)

        # then, remove a previous definition from the gen set if its left-hand side is redefined
        gen_block_copy = gen_block.copy()
        for definition in gen_block_copy:
            try:
                # don't remove what we've just added
                if definition == insn:
                    continue
                if definition.args[0] == insn.args[0]:
                    gen_block.remove(definition)
                    continue
                if definition.args[0].ref_obj and definition.args[0].ref_obj == insn.args[0]:
                    gen_block.remove(definition)
                    continue
                # for definitions like reg:v2 = {}, a subsequent reg:v2["abc"] = acc should cause the removal of reg:v2
                if insn.args[0].ref_obj and insn.args[0].ref_obj == definition.args[0]:
                    gen_block.remove(definition)
                    continue
                # for nested ExprArg
                vars_used_in_expr = []
                for arg in definition.args[1:]:
                    if isinstance(arg, ExprArg):
                        vars_used_in_expr.extend(arg.get_used_args())
                if insn.args[0] in vars_used_in_expr:
                    gen_block.remove(definition)
                    continue
            except KeyError:
                pass

    def reaching_definitions(self, method: IRMethod, rpo: typing.List[IRBlock], gen, kill):
        in_block, out_block = {}, {}
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
                    in_block[block] = in_b

                    old_out_block = out_block.copy()
                    out_block[block] = gen[block].union(in_block[block].difference(kill[block]))
                    if old_out_block != out_block:
                        out_changed = True

        # remove the dummy blocks
        method.blocks[0].remove_predecessor(entry_block)
        for block in no_successor_blocks:
            block.remove_successor(exit_block)

        return in_block, out_block

    def is_no_successor_block(self, block: IRBlock):
        return len(block.successors) == 0
