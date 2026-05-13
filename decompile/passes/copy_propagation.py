import typing

from ordered_set import OrderedSet

from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType, NAddressCode
from decompile.method_pass import MethodPass
from decompile.passes.reaching_def import ReachingDefinitions
from decompile.passes.reverse_postorder import ReversePostorder
from pandasm.insn import PandasmInsnArgument


class CopyPropagation(MethodPass):
    def __init__(self, in_r, constrained=False):
        super().__init__()
        self.in_r = in_r
        self.constrained = constrained

    def run_on_method(self, method: IRMethod):
        gen, kill = {}, {}
        copies = self.collect_copies(method)
        for block in method.blocks:
            gen[block], kill[block] = self.analyze_gen_kill(block, copies)

        rpo = ReversePostorder().run_on_method(method)
        in_c, out_c = self.copy_propagation(method, rpo, gen, kill, copies)
        self.replace_copies(copies, in_c, self.in_r)
        return in_c, out_c

    def analyze_gen_kill(self, block: IRBlock, copies, stop_on_insn=None):
        gen_block, kill_block = OrderedSet(), OrderedSet()
        def_block = OrderedSet()

        for insn in block.insns:
            if stop_on_insn == insn:
                break
            if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL]:
                self.analyze_assign(insn, def_block, gen_block)

        for copy_ in copies:
            if copy_.src2 is None:
                copy_args = {copy_.dst, copy_.src}
                for definition in def_block:
                    if definition.dst in copy_args:
                        # if for this copy, say x=y, either x or y is redefined in this block, then add it to kill set
                        kill_block.add(copy_)
                    # another case is instructions like acc = reg:v2["abc"], where the array access is treated as one
                    # argument, but actually uses reg:v2 AND "abc" separately
                    # in this case, reg:v2 being redefined also means the copy no longer has
                    # the original value, i.e. killed
                    if copy_.src.ref_obj:
                        # if reg:v2 is redefined, add it to kill set
                        if definition.dst == copy_.src.ref_obj:
                            kill_block.add(copy_)
            else:
                copy_args = {copy_.dst, copy_.src, copy_.src2}
                for definition in def_block:
                    if definition.dst in copy_args:
                        # if for this copy, say x=y+z, any of x, y and z is redefined in this block, add it to kill set
                        kill_block.add(copy_)
            # there could be nested ExprArgs on rhs, take any arguments in ExprArg into account
            for definition in def_block:
                vars_used_in_copy = set()
                for arg in copy_.args[1:]:
                    if isinstance(arg, ExprArg):
                        vars_used_in_copy.update(arg.get_used_args())
                if definition.dst in vars_used_in_copy:
                    kill_block.add(copy_)

        return gen_block, kill_block

    def collect_copies(self, method: IRMethod, stop_on_insn=None):
        copies = OrderedSet()
        for block in method.blocks:
            for insn in block.insns:
                if insn == stop_on_insn:
                    break
                if insn.type == NAddressCodeType.ASSIGN:
                    copies.add(insn)
        return copies

    def analyze_assign(self, insn: NAddressCode, def_block, gen_block):
        def_block.add(insn)

        # gen is the set of copies (x=y) defined in this block without x or y being subsequently redefined in it
        # first add to the set this assign (i.e. copy) instruction — only for ASSIGN, not CALL
        # (CALL still updates def_block and kills existing gen entries below)
        if insn.type == NAddressCodeType.ASSIGN:
            gen_block.add(insn)

        # then, remove a previous copy from the gen set if any argument in it is redefined
        gen_block_copy = gen_block.copy()
        for copy in gen_block_copy:
            try:
                # don't remove what we've just added
                if copy == insn:
                    continue
                if copy.dst == insn.dst:
                    gen_block.remove(copy)
                    continue
                if copy.src == insn.dst:
                    gen_block.remove(copy)
                    continue
                # for nested ExprArg
                vars_used_in_expr = []
                for arg in copy.args[1:]:
                    if isinstance(arg, ExprArg):
                        vars_used_in_expr.extend(arg.get_used_args())
                if insn.dst in vars_used_in_expr:
                    gen_block.remove(copy)
                    continue
                # for copies like acc = reg:v2["abc"], where a subsequent redefinition of reg:v2 should cause a removal
                if copy.src.ref_obj and insn.dst == copy.src.ref_obj:
                    gen_block.remove(copy)
                    continue
                # for copies like reg:v2 = {}, a subsequent reg:v2["abc"] = acc should cause the removal of reg:v2
                if insn.dst.ref_obj and insn.dst.ref_obj == copy.dst:
                    gen_block.remove(copy)
                    continue
                # for three-argument ASSIGN case, take src2 into account
                if copy.src2 is not None:
                    if insn.dst == copy.src2:
                        gen_block.remove(copy)
                        continue
                    if copy.src2.ref_obj and insn.dst == copy.src2.ref_obj:
                        gen_block.remove(copy)
                        continue
            except KeyError:
                pass

    def copy_propagation(self, method: IRMethod, rpo: typing.List[IRBlock], gen, kill, copies):
        in_block, out_block = {}, {}
        entry_block = method.blocks[0]
        extended_block_list = rpo
        in_block[entry_block] = OrderedSet()
        out_block[entry_block] = gen[entry_block]
        for block in extended_block_list:
            if block != entry_block:
                in_block[block] = copies
                out_block[block] = copies  # this is needed for methods containing loops

        out_changed = False
        first_time = True
        while out_changed or first_time:
            out_changed = False
            first_time = False
            for block in extended_block_list:
                if block != entry_block:
                    if block.predecessors:
                        in_b = out_block[block.predecessors[0]]
                        for pred in block.predecessors[1:]:
                            in_b = in_b.intersection(out_block[pred])
                    else:
                        in_b = OrderedSet()
                    in_block[block] = in_b

                    old_out_block = out_block.copy()
                    out_block[block] = gen[block].union(in_block[block].difference(kill[block]))
                    if old_out_block != out_block:
                        out_changed = True

        return in_block, out_block

    def is_no_successor_block(self, block: IRBlock):
        return len(block.successors) == 0

    def replace_copies(self, copies, in_c, in_r):
        # Single-pass, block-level replacement to avoid repeated collect/analyze per copy+insn
        # Track per-copy state across the whole method
        replaced_once_map = {c: False for c in copies}
        all_uses_replaced_map = {c: True for c in copies}

        # helper to determine whether a definition insn kills a copy
        def def_kills_copy(def_insn, copy_):
            try:
                if copy_.src2 is None:
                    copy_args = {copy_.dst, copy_.src}
                    if def_insn.dst in copy_args:
                        return True
                    if copy_.src.ref_obj and def_insn.dst == copy_.src.ref_obj:
                        return True
                else:
                    copy_args = {copy_.dst, copy_.src, copy_.src2}
                    if def_insn.dst in copy_args:
                        return True
                # nested ExprArg usage
                vars_used_in_copy = set()
                for arg in copy_.args[1:]:
                    if isinstance(arg, ExprArg):
                        vars_used_in_copy.update(arg.get_used_args())
                if def_insn.dst in vars_used_in_copy:
                    return True
            except Exception:
                return False
            return False

        # iterate over blocks and do a forward single-pass
        for block, copies_reaching_block in in_c.items():
            # current set of copies available at the current program point
            current_copies = copies_reaching_block.copy()
            # per-block definition/gen tracking to maintain kills for this block
            def_block = OrderedSet()
            gen_block = OrderedSet()

            for insn in block.insns:
                # compute vars used in this insn
                vars_use = set()
                if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL]:
                    vars_use = self.analyze_assign_for_replace(insn)
                elif insn.type in [NAddressCodeType.COND_JUMP, NAddressCodeType.COND_THROW]:
                    vars_use = self.analyze_cond_jump_throw_for_replace(insn)

                # try replacing uses using current_copies
                for copy_ in list(current_copies):
                    # in constrained mode, only replace copies of the form x=y (one argument on the rhs) for simplicity
                    if copy_.src2 is not None and self.constrained:
                        continue
                    if copy_.dst in vars_use:
                        # if copy is currently reaching this insn, attempt replacement
                        if copy_ in current_copies:
                            if self.replace_var_use(insn, copy_):
                                replaced_once_map[copy_] = True
                            else:
                                all_uses_replaced_map[copy_] = False
                        else:
                            # conservative fallback: if it's not in current_copies but reaches block overall, mark not replaceable
                            if copy_ in in_r.get(block, OrderedSet()):
                                all_uses_replaced_map[copy_] = False

                # now update def/gen info with this insn (if it's a defining insn)
                if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL]:
                    # treat this insn as a new definition; update def_block/gen_block
                    self.analyze_assign(insn, def_block, gen_block)

                    # applying kill logic: a new definition may kill copies in current_copies
                    for copy_ in list(current_copies):
                        if def_kills_copy(insn, copy_):
                            try:
                                current_copies.remove(copy_)
                            except KeyError:
                                pass

                    # if this insn itself is an ASSIGN copy, add to current_copies (so later insns can see it)
                    if insn.type == NAddressCodeType.ASSIGN:
                        current_copies.add(insn)

            # end of block

        # after scanning all blocks, remove copies that were replaced everywhere and at least once
        for copy_ in list(copies):
            if replaced_once_map.get(copy_, False) and all_uses_replaced_map.get(copy_, True):
                copy_.erase_from_parent()

    def analyze_assign_for_replace(self, insn: NAddressCode):
        vars_use = OrderedSet([insn.args[1]])
        if isinstance(insn.args[1], ExprArg):
            vars_use.update(insn.args[1].get_used_args())
        if insn.dst.ref_obj:
            vars_use.add(insn.dst.ref_obj)
        if insn.args[1].ref_obj:
            vars_use.add(insn.args[1].ref_obj)
        for arg in insn.args[1:]:
            vars_use.add(arg)
            if arg.ref_obj:
                vars_use.add(arg.ref_obj)
            # for nested ExprArg
            if isinstance(arg, ExprArg):
                vars_use.update(arg.get_used_args())
        return vars_use

    def analyze_cond_jump_throw_for_replace(self, insn: NAddressCode):
        vars_use = OrderedSet()
        for arg in insn.args:
            vars_use.add(arg)
            if arg.ref_obj:
                vars_use.add(arg.ref_obj)
        return vars_use

    def replace_var_use(self, insn: NAddressCode, copy_):
        are_all_args_replaced = True
        var_to_replace, copy_op, copy_comment = copy_.dst, copy_.op, copy_.comment
        if (self.constrained and copy_.src.ref_obj) or (not self.constrained and var_to_replace == copy_.src.ref_obj):
            # in cases like "acc = acc['xxx']", when var_to_replace == acc, and copy_.src == acc['xxx'],
            # replacing results in infinite recursion ("acc['xxx'] = acc['xxx']['xxx'] and so on), so skip it
            return False
        if var_to_replace.ref_obj:
            # reference object could be accessible outside this method, replacing could render a store to it
            # dead code and wrongly eliminated, see analyze_assign() in DeadCodeElimination for example
            return False
        if copy_.src.type == 'object':
            # objects are typically new()ed and shouldn't be propagated, or else there'll be multiple new objects
            return False
        if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL, NAddressCodeType.COND_JUMP, NAddressCodeType.COND_THROW]:
            for idx, arg in enumerate(insn.args):
                if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL] and idx == 0 and var_to_replace == insn.dst:
                    # don't replace a definition, for example
                    #    v1 = v1 + 3
                    # if var_to_replace == v1, we should only replace v1 on the rhs, not on the lhs, but it's ok if
                    #    v1['xxx'] = v1['xxx'] + 3
                    # because v1 on lhs is not a definition but a use
                    continue
                if arg == var_to_replace:
                    if copy_.src2 is None and copy_op == '':
                        # copy is of the form x=y (simple copy, no operator on rhs)
                        insn.replace_arg(idx, copy_.src)
                    else:
                        # copy is of the form x=uop y or x=y bop z
                        rhs = [copy_.src] if copy_.src2 is None else [copy_.src, copy_.src2]
                        insn.replace_arg(idx, ExprArg(rhs, 'arith', copy_.op))
                if arg.ref_obj and arg.ref_obj == var_to_replace:
                    if copy_.src2 is None:
                        arg.ref_obj = copy_.src
                    else:
                        # copy has more than one argument on rhs — can't substitute a ref_obj
                        # for readability, don't replace it for now
                        are_all_args_replaced = False
                        continue
                if copy_comment:
                    # if the original copy has a comment, append it to this instruction
                    # because copy propagation could render the original copy dead code and
                    # therefore eliminated
                    insn.comment = copy_comment
        return are_all_args_replaced