from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCodeType, NAddressCode
from decompile.method_pass import MethodPass
from pandasm.insn import PandasmInsnArgument


class DefUseAnalysis(MethodPass):
    def run_on_method(self, method: IRMethod):
        # compute def and use sets for all blocks
        for block in method.blocks:
            self.analyze_block(block)

    def analyze_block(self, block: IRBlock):
        defs, uses = set(), set()
        for insn in block.insns:
            if insn.type == NAddressCodeType.ASSIGN:
                self.analyze_assign(insn, defs, uses)
            elif insn.type in [NAddressCodeType.UNCOND_JUMP, NAddressCodeType.UNCOND_THROW]:
                self.analyze_uncond_jump_throw(insn, defs, uses)
            elif insn.type in [NAddressCodeType.COND_JUMP, NAddressCodeType.COND_THROW]:
                self.analyze_cond_jump_throw(insn, defs, uses)
            elif insn.type == NAddressCodeType.RETURN:
                self.analyze_return(insn, defs, uses)
            elif insn.type == NAddressCodeType.CALL:
                self.analyze_call(insn, defs, uses)
            elif insn.type == NAddressCodeType.UNKNOWN:
                self.analyze_unknown(insn, defs, uses)

        block.defs, block.uses = defs, uses
        return defs, uses

    def analyze_assign(self, insn: NAddressCode, defs, uses):
        defined, used1, used2 = False, False, False
        ref_obj_used1, ref_obj_used2, ref_obj_used3 = False, False, False
        if insn.args[0] not in uses:
            defined = True
        if insn.args[0].ref_obj and insn.args[0].ref_obj not in defs:
            ref_obj_used1 = True
        if insn.args[1] not in defs:
            used1 = True
        if insn.args[1].ref_obj and insn.args[1].ref_obj not in defs:
            ref_obj_used2 = True

        # for nested ExprArg
        vars_used_in_expr = []
        for arg in insn.args[1:]:
            if isinstance(arg, ExprArg):
                vars_used_in_expr.extend(arg.get_used_args())
        vars_used_in_expr_is_undefined = set()
        for var in vars_used_in_expr:
            if var not in defs:
                vars_used_in_expr_is_undefined.add(var)

        if len(insn.args) == 3:
            # x = y bop z, we need to add z
            if insn.args[2] not in defs:
                used2 = True
            if insn.args[2].ref_obj and insn.args[2].ref_obj not in defs:
                ref_obj_used3 = True
        if defined:
            defs.add(insn.args[0])
        if used1:
            uses.add(insn.args[1])
        if used2:
            uses.add(insn.args[2])
        if ref_obj_used1:
            uses.add(insn.args[0].ref_obj)
        if ref_obj_used2:
            uses.add(insn.args[1].ref_obj)
        if ref_obj_used3:
            uses.add(insn.args[2].ref_obj)
        for var in vars_used_in_expr:
            if var in vars_used_in_expr_is_undefined:
                uses.add(var)

    def analyze_uncond_jump_throw(self, insn: NAddressCode, defs, uses):
        used, ref_obj_used = False, False
        if insn.args[0] not in defs:
            used = True
        if insn.args[0].ref_obj and insn.args[0].ref_obj not in defs:
            ref_obj_used = True
        if used:
            uses.add(insn.args[0])
        if ref_obj_used:
            uses.add(insn.args[0].ref_obj)

    def analyze_cond_jump_throw(self, insn: NAddressCode, defs, uses):
        used1, used2, used3 = False, False, False
        ref_obj_used1, ref_obj_used2, ref_obj_used3 = False, False, False
        if insn.args[0] not in defs:
            used1 = True
        if insn.args[0].ref_obj and insn.args[0].ref_obj not in defs:
            ref_obj_used1 = True
        if insn.args[1] not in defs:
            used2 = True
        if insn.args[1].ref_obj and insn.args[1].ref_obj not in defs:
            ref_obj_used2 = True
        if len(insn.args) == 3:
            # if x rop y jump/throw L, we need to add L
            if insn.args[2] not in defs:
                used3 = True
            if insn.args[2].ref_obj and insn.args[2].ref_obj not in defs:
                ref_obj_used3 = True
        if used1:
            uses.add(insn.args[0])
        if used2:
            uses.add(insn.args[1])
        if used3:
            uses.add(insn.args[2])
        if ref_obj_used1:
            uses.add(insn.args[0].ref_obj)
        if ref_obj_used2:
            uses.add(insn.args[1].ref_obj)
        if ref_obj_used3:
            uses.add(insn.args[2].ref_obj)


    def analyze_return(self, insn: NAddressCode, defs, uses):
        used, ref_obj_used = False, False
        if insn.args[0] not in defs:
            used = True
        if insn.args[0].ref_obj and insn.args[0].ref_obj not in defs:
            ref_obj_used = True
        if used:
            uses.add(insn.args[0])
        if ref_obj_used:
            uses.add(insn.args[0].ref_obj)

    def analyze_call(self, insn: NAddressCode, defs, uses):
        defined, used = False, [False] * len(insn.args[1:])
        ref_obj_used1, ref_obj_used_remaining = False, [False] * len(insn.args[1:])
        if insn.args[0] not in uses:
            defined = True
        if insn.args[0].ref_obj and insn.args[0].ref_obj not in defs:
            ref_obj_used1 = True

        # for nested ExprArg
        vars_used_in_expr = []
        for arg in insn.args[1:]:
            if isinstance(arg, ExprArg):
                vars_used_in_expr.extend(arg.get_used_args())
        vars_used_in_expr_is_undefined = set()
        for var in vars_used_in_expr:
            if var not in defs:
                vars_used_in_expr_is_undefined.add(var)

        for idx, arg in enumerate(insn.args[1:]):
            if arg not in defs:
                used[idx] = True
            if arg.ref_obj and arg.ref_obj not in defs:
                ref_obj_used_remaining[idx] = True

        if defined:
            defs.add(insn.args[0])
        if ref_obj_used1:
            uses.add(insn.args[0].ref_obj)
        for idx, arg in enumerate(insn.args[1:]):
            if used[idx]:
                uses.add(arg)
            if ref_obj_used_remaining[idx]:
                uses.add(arg.ref_obj)
        for var in vars_used_in_expr:
            if var in vars_used_in_expr_is_undefined:
                uses.add(var)

    def analyze_unknown(self, insn: NAddressCode, defs, uses):
        """
        for UNKNOWN NACs, since we don't know what this NAC does, we must assume the worst scenario:
        all operands involved are defined, but no operand is used (i.e. all killed without regeneration)
        """
        for operand in insn.args:
            # some heuristics to infer what type this operand is
            if operand == 'acc':
                acc = PandasmInsnArgument('acc')
                defs.add(acc)
            elif operand.startswith('a') or operand.startswith('v'):
                reg = PandasmInsnArgument('reg', operand)
                defs.add(reg)
            elif operand.startswith('0x') or operand.startswith('"') or operand.startswith('jump_label') or operand.startswith('com.'):
                # immediates, strings, jump labels and functions are constants, so these are not targets of our analysis
                pass
