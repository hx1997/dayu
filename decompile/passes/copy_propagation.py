from ordered_set import OrderedSet

from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType, NAddressCode
from decompile.method_pass import MethodPass
from decompile.passes.reaching_def import ReachingDefinitions
from pandasm.insn import PandasmInsnArgument


class CopyPropagation(MethodPass):
    def __init__(self, in_r, constrained=False):
        self.in_r = in_r
        self.constrained = constrained

    def run_on_method(self, method: IRMethod):
        gen, kill = {}, {}
        copies = self.collect_copies(method)
        for block in method.blocks:
            gen[block], kill[block] = self.analyze_gen_kill(block, copies)
        in_c, out_c = self.copy_propagation(method, gen, kill, copies)
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
            if len(copy_.args) == 2:
                for definition in def_block:
                    if definition.args[0] in [copy_.args[0], copy_.args[1]]:
                        # if for this copy, say x=y, either x or y is redefined in this block, then add it to kill set
                        kill_block.add(copy_)
                    # another case is instructions like acc = reg:v2["abc"], where the array access is treated as one
                    # argument, but actually uses reg:v2 AND "abc" separately
                    # in this case, reg:v2 being redefined also means the copy no longer has
                    # the original value, i.e. killed
                    if copy_.args[1].ref_obj:
                        # if reg:v2 is redefined, add it to kill set
                        if definition.args[0] == copy_.args[1].ref_obj:
                            kill_block.add(copy_)
            elif len(copy_.args) >= 3:
                for definition in def_block:
                    if definition.args[0] in [copy_.args[0], copy_.args[1], *copy_.args[2:]]:
                        # if for this copy, say x=y+z, any of x, y and z is redefined in this block, add it to kill set
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

    def collect_copies(self, method: IRMethod, stop_on_insn=None):
        copies = OrderedSet()
        for block in method.blocks:
            for insn in block.insns:
                if insn == stop_on_insn:
                    break
                if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL]:
                    copies.add(insn)
        return copies

    def analyze_assign(self, insn: NAddressCode, def_block, gen_block):
        def_block.add(insn)

        # gen is the set of copies (x=y) defined in this block without x or y being subsequently redefined in it
        # first add to the set this assign (i.e. copy) instruction
        if len(insn.args) == 2:
            gen_block.add(insn)
        elif len(insn.args) >= 3:
            # for the three-argument ASSIGN case x=y+z and the CALL case x = y(z1,z2,...)
            gen_block.add(insn)

        # then, remove a previous copy from the gen set if any argument in it is redefined
        gen_block_copy = gen_block.copy()
        for copy in gen_block_copy:
            try:
                # don't remove what we've just added
                if copy == insn:
                    continue
                if copy.args[0] == insn.args[0]:
                    gen_block.remove(copy)
                    continue
                if copy.args[1] == insn.args[0]:
                    gen_block.remove(copy)
                    continue
                # for nested ExprArg
                vars_used_in_expr = []
                for arg in copy.args[1:]:
                    if isinstance(arg, ExprArg):
                        vars_used_in_expr.extend(arg.get_used_args())
                if insn.args[0] in vars_used_in_expr:
                    gen_block.remove(copy)
                    continue
                # for copies like acc = reg:v2["abc"], where a subsequent redefinition of reg:v2 should cause a removal
                if copy.args[1].ref_obj and insn.args[0] == copy.args[1].ref_obj:
                    gen_block.remove(copy)
                    continue
                # for copies like reg:v2 = {}, a subsequent reg:v2["abc"] = acc should cause the removal of reg:v2
                if insn.args[0].ref_obj and insn.args[0].ref_obj == copy.args[0]:
                    gen_block.remove(copy)
                    continue
                # for three-argument ASSIGN case and the CALL case, take any additional arguments on rhs into account
                if len(copy.args) >= 3:
                    extra_args = copy.args[2:]
                    if insn.args[0] in extra_args:
                        gen_block.remove(copy)
                        continue
                    # for acc = reg:v0 + reg:v2["abc"]... does this ever show up? dunno, just playing safe here
                    for arg in extra_args:
                        if arg.ref_obj and insn.args[0] == arg.ref_obj:
                            gen_block.remove(copy)
                            continue
            except KeyError:
                pass

    def copy_propagation(self, method: IRMethod, gen, kill, copies):
        in_block, out_block = {}, {}
        entry_block = method.blocks[0]
        extended_block_list = [entry_block, *method.blocks[1:]]
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
        # TODO: revamp this suuuuuuuuper slow method by optimizing away the repeated instruction-level
        #  copy propagation
        for copy_ in copies:
            replaced_once = False
            are_all_uses_replaced = True
            for block, copies_reaching_block in in_c.items():
                if len(copy_.args) >= 3 and self.constrained:
                    # in constrained mode, only replace copies of the form x=y (one argument on the rhs) for simplicity
                    continue
                if copy_.type == NAddressCodeType.CALL:
                    # don't replace if the copy is a function call, because this can lead to multiple calls of the
                    # same function, which changes the original semantics
                    continue

                for insn in block.insns:
                    vars_use = set()
                    if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL]:
                        vars_use = self.analyze_assign_for_replace(insn)
                    elif insn.type in [NAddressCodeType.COND_JUMP, NAddressCodeType.COND_THROW]:
                        vars_use = self.analyze_cond_jump_throw_for_replace(insn)
                    if copy_.args[0] in vars_use:
                        # TODO: these two statements are repeated for each copy and for each instruction in the block,
                        #  which is extremely time-consuming
                        copies_until_this_insn = self.collect_copies(block.parent_method, stop_on_insn=insn)
                        gen, kill = self.analyze_gen_kill(block, copies_until_this_insn, stop_on_insn=insn)
                        if copy_ in copies_reaching_block.difference(kill).union(gen):
                            # we have to make sure all uses of this copy can be replaced before we can remove the copy;
                            # if any single replacement can't be done, it would be wrong to remove, e.g.,
                            #    (1) v2 = a2
                            #    (2) acc = v2 + 'def'
                            #    (3) v3 = v2 + 'nnn'
                            # if the v2 in (2) can't be replaced by a2, but the v2 in (3) can, we can't remove (1),
                            # because that would leave v2 in (2) undefined
                            if self.replace_var_use(insn, copy_):
                                replaced_once = True
                            else:
                                are_all_uses_replaced = False
                        else:  # definition reaches this use, don't remove
                            gen, kill = ReachingDefinitions.analyze_gen_kill(block, copies_until_this_insn, stop_on_insn=insn)
                            if copy_ in in_r[block].difference(kill).union(gen):
                                are_all_uses_replaced = False
            # if all uses reached by this copy can be replaced, we can safely do the replacement
            # and remove the copy instruction
            if replaced_once and are_all_uses_replaced:
                copy_.erase_from_parent()

    def analyze_assign_for_replace(self, insn: NAddressCode):
        vars_use = OrderedSet([insn.args[1]])
        if isinstance(insn.args[1], ExprArg):
            vars_use.update(insn.args[1].get_used_args())
        if insn.args[0].ref_obj:
            vars_use.add(insn.args[0].ref_obj)
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
        var_to_replace, replace_with, copy_op, copy_comment = copy_.args[0], copy_.args[1:], copy_.op, copy_.comment
        if (self.constrained and replace_with[0].ref_obj) or (not self.constrained and var_to_replace == replace_with[0].ref_obj):
            # in cases like "acc = acc['xxx']", when var_to_replace == acc, and replace_with == acc['xxx'],
            # replacing results in infinite recursion ("acc['xxx'] = acc['xxx']['xxx'] and so on), so skip it
            return False
        if copy_op and self.constrained:
            # an ASSIGN NAC can only take at most one operator on the rhs
            # for cases like:
            #   acc = -v2
            #   v3 = acc + v4
            # if var_to_replace == acc, replace_with == v2, and copy_op == '-', this will become
            #   acc = -v2
            #   v3 = -v2 + v4
            # violating the ASSIGN NAC format
            return False
        if var_to_replace.type.startswith('lexenv'):
            # we don't want to replace newlexenv instructions either, because this could render it dead code
            # and wrongly eliminated, for example:
            #    lexenv_xxx = array:yyy
            #    acc = lexenv_xxx
            # if replaced this will become:
            #    lexenv_xxx = array:yyy
            #    acc = array:yyy
            # making the first instruction dead, which is suboptimal as the first instruction is actually
            # a "new" statement (i.e. lexenv_xxx = new array:yyy) and not an ordinary assignment
            return False
        if var_to_replace.ref_obj:
            # reference object could be accessible outside this method, replacing could render a store to it
            # dead code and wrongly eliminated, see analyze_assign() in DeadCodeElimination for example
            return False
        if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL, NAddressCodeType.COND_JUMP, NAddressCodeType.COND_THROW]:
            for idx, arg in enumerate(insn.args):
                if insn.type in [NAddressCodeType.ASSIGN, NAddressCodeType.CALL] and idx == 0 and var_to_replace == insn.args[0]:
                    # don't replace a definition, for example
                    #    v1 = v1 + 3
                    # if var_to_replace == v1, we should only replace v1 on the rhs, not on the lhs, but it's ok if
                    #    v1['xxx'] = v1['xxx'] + 3
                    # because v1 on lhs is not a definition but a use
                    continue
                if arg == var_to_replace:
                    if len(replace_with) == 1:
                        if copy_op == '':
                            # copy is of the form x=y (one argument with no operator on rhs)
                            insn.args[idx] = replace_with[0]
                        else:
                            # copy is of the form x=uop y
                            if copy_.type is NAddressCodeType.ASSIGN:
                                insn.args[idx] = ExprArg(replace_with, 'arith', copy_.op)
                            elif copy_.type is NAddressCodeType.CALL:
                                insn.args[idx] = ExprArg(replace_with, 'call', copy_.op)
                    elif len(replace_with) > 1:
                        # copy is of the form x=y bop z or x=func(y) (two-or-more-argument expression on rhs)
                        if copy_.type is NAddressCodeType.ASSIGN:
                            insn.args[idx] = ExprArg(replace_with, 'arith', copy_.op)
                        elif copy_.type is NAddressCodeType.CALL:
                            insn.args[idx] = ExprArg(replace_with, 'call', copy_.op)
                if arg.ref_obj and arg.ref_obj == var_to_replace:
                    if len(replace_with) == 1:
                        insn.args[idx].ref_obj = replace_with[0]
                    else:
                        # this case means insn has a reference object (i.e. var_to_replace) and replace_with has more than one argument on rhs
                        # for example, insn is "v4 = acc['delete']" and replace_with represents a function call foo(...)
                        # if replaced this will become "v4 = foo(...)['delete']" which can be hard to read if the func call has many arguments
                        # for readability, don't replace it for now
                        are_all_args_replaced = False
                        continue
                if copy_comment:
                    # if the original copy has a comment, append it to this instruction
                    # because copy propagation could render the original copy dead code and
                    # therefore eliminated
                    insn.comment = copy_comment
        return are_all_args_replaced