import typing

from decompile.ir.basicblock import IRBlock
from decompile.ir.nac import (AssignNAC, CallNAC, CondJumpNAC, CondThrowNAC,
                               ImportNAC, NAddressCodeType, ReturnNAC,
                               UncondJumpNAC, UncondThrowNAC, VarDeclNAC)
from pandasm.insn import PandasmInsnArgument


class IRBuilder:
    def __init__(self, module):
        self.module = module
        # insertion point is a tuple (IRBlock, index of instruction in the block)
        self.insert_point: typing.Tuple[IRBlock, int] = None

    def set_insert_point(self, block: IRBlock, insn_index=-1):
        if insn_index == -1:
            # -1 means insert at the end
            self.insert_point = (block, len(block.insns))
        else:
            self.insert_point = (block, insn_index)

    def increment_insert_point(self):
        self.set_insert_point(self.insert_point[0], self.insert_point[1] + 1)

    def insert(self, insn):
        insn.parent_block = self.insert_point[0]
        self.insert_point[0].insert_insn(insn, self.insert_point[1])
        self.increment_insert_point()

    def create_assign(self, src: PandasmInsnArgument, dst: typing.Union[PandasmInsnArgument, None] = None, label='', extra_info=None):
        if not dst:
            dst = PandasmInsnArgument('acc')
        insn = AssignNAC(op='', dst=dst, src=src, label_name=label, extra_info=extra_info)
        self.insert(insn)

    def create_assign_rhs_uop(self, src: PandasmInsnArgument, dst: typing.Union[PandasmInsnArgument, None] = None, rhs_op='', label=''):
        assert rhs_op != ''
        if not dst:
            dst = PandasmInsnArgument('acc')
        insn = AssignNAC(op=rhs_op, dst=dst, src=src, label_name=label)
        self.insert(insn)

    def create_assign_rhs_bop(self, src1: PandasmInsnArgument, src2: PandasmInsnArgument, dst: typing.Union[PandasmInsnArgument, None] = None, rhs_op='', label=''):
        assert rhs_op != ''
        if not dst:
            dst = PandasmInsnArgument('acc')
        insn = AssignNAC(op=rhs_op, dst=dst, src=src1, src2=src2, label_name=label)
        self.insert(insn)

    def create_uncond_jump(self, target: PandasmInsnArgument, label=''):
        # connect this block to the target block in the CFG
        target_nac = self.insert_point[0].parent_method.get_insn_by_label(target.value)
        if not target_nac:
            raise Exception(f'{self.__class__.__name__}: unconditional jump to a non-existent label')
        target_block = target_nac.parent_block
        self.insert_point[0].add_successor(target_block)

        insn = UncondJumpNAC(target=target, label_name=label)
        self.insert(insn)

    def create_cond_jump(self, cond_arg1, cond_arg2, rop, target: PandasmInsnArgument, label=''):
        # connect this block to the target block in the CFG
        target_nac = self.insert_point[0].parent_method.get_insn_by_label(target.value)
        if not target_nac:
            raise Exception(f'{self.__class__.__name__}: conditional jump to a non-existent label')
        target_block = target_nac.parent_block
        self.insert_point[0].add_successor(target_block)

        insn = CondJumpNAC(op=rop, cond1=cond_arg1, cond2=cond_arg2, target=target, label_name=label)
        self.insert(insn)

    def create_call(self, func: PandasmInsnArgument, args: typing.List[PandasmInsnArgument],
                    dst: typing.Union[PandasmInsnArgument, None] = None, label='', comment='', extra_info=None):
        if not dst:
            dst = PandasmInsnArgument('acc')
        insn = CallNAC(func=func, call_args=args, dst=dst, label_name=label, comment=comment, extra_info=extra_info)
        self.insert(insn)

    def create_return(self, retval: typing.Union[PandasmInsnArgument, None] = None, label=''):
        # a return instruction marks the end of a basic block, so split the block from here if there are more
        # instructions after this one
        next_insn_idx = self.insert_point[1] + 1
        if next_insn_idx < len(self.insert_point[0].insns):
            next_insn = self.insert_point[0].insns[next_insn_idx]
            self.insert_point[0].split_block(next_insn, False)

        if not retval:
            retval = PandasmInsnArgument('acc')
        insn = ReturnNAC(retval=retval, label_name=label)
        self.insert(insn)

    def create_uncond_throw(self, exception: PandasmInsnArgument, label=''):
        # an unconditional throw marks the end of a basic block; split here if there are more instructions
        # after this one. Exception handlers are modeled separately from ordinary CFG edges,
        # so neither conditional nor unconditional throws add handler successors here.
        next_insn_idx = self.insert_point[1] + 1
        if next_insn_idx < len(self.insert_point[0].insns):
            next_insn = self.insert_point[0].insns[next_insn_idx]
            self.insert_point[0].split_block(next_insn, False)

        insn = UncondThrowNAC(exception=exception, label_name=label)
        self.insert(insn)

    def create_cond_throw(self, cond_arg1, cond_arg2, rop, exception: PandasmInsnArgument, label=''):
        # a conditional throw (e.g. throw.undefinedifholewithname) does not split the basic block;
        # exception handling is recovered at the structural region level via try_regions metadata,
        # not via per-instruction CFG edges.
        insn = CondThrowNAC(op=rop, cond1=cond_arg1, cond2=cond_arg2, exception=exception, label_name=label)
        self.insert(insn)

    def create_import(self, imported_var, local_name, import_from_module, label=''):
        insn = ImportNAC(imported=imported_var, local_name=local_name, module=import_from_module, label_name=label)
        self.insert(insn)

    def create_var_decl(self, var_names, label='', extra_info=None):
        insn = VarDeclNAC(var_names=var_names, label_name=label, extra_info=extra_info)
        self.insert(insn)
