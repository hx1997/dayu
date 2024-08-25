import typing
from enum import IntEnum, auto

from decompile.ir.basicblock import IRBlock
from decompile.ir.nac import NAddressCode, NAddressCodeType
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

    def create_assign(self, src: PandasmInsnArgument, dst: typing.Union[PandasmInsnArgument, None] = None, label=''):
        if not dst:
            dst = PandasmInsnArgument('acc')
        insn = NAddressCode('', [dst, src], label_name=label)
        self.insert(insn)

    def create_assign_rhs_uop(self, src: PandasmInsnArgument, dst: typing.Union[PandasmInsnArgument, None] = None, rhs_op='', label=''):
        assert rhs_op != ''
        if not dst:
            dst = PandasmInsnArgument('acc')
        insn = NAddressCode(rhs_op, [dst, src], label_name=label)
        self.insert(insn)

    def create_assign_rhs_bop(self, src1: PandasmInsnArgument, src2: PandasmInsnArgument, dst: typing.Union[PandasmInsnArgument, None] = None, rhs_op='', label=''):
        assert rhs_op != ''
        if not dst:
            dst = PandasmInsnArgument('acc')
        insn = NAddressCode(rhs_op, [dst, src1, src2], label_name=label)
        self.insert(insn)

    def create_uncond_jump(self, target: PandasmInsnArgument, label=''):
        # connect this block to the target block in the CFG
        target_nac = self.insert_point[0].parent_method.get_insn_by_label(target.value)
        if not target_nac:
            raise Exception(f'{self.__class__.__name__}: unconditional jump to a non-existent label')
        target_block = target_nac.parent_block
        self.insert_point[0].add_successor(target_block)

        insn = NAddressCode('', [target], NAddressCodeType.UNCOND_JUMP, label_name=label)
        self.insert(insn)

    def create_cond_jump(self, cond_arg1, cond_arg2, rop, target: PandasmInsnArgument, label=''):
        # connect this block to the target block in the CFG
        target_nac = self.insert_point[0].parent_method.get_insn_by_label(target.value)
        if not target_nac:
            raise Exception(f'{self.__class__.__name__}: conditional jump to a non-existent label')
        target_block = target_nac.parent_block
        self.insert_point[0].add_successor(target_block)

        insn = NAddressCode(rop, [cond_arg1, cond_arg2, target], NAddressCodeType.COND_JUMP, label_name=label)
        self.insert(insn)

    def create_call(self, func: PandasmInsnArgument, args: typing.List[PandasmInsnArgument],
                    dst: typing.Union[PandasmInsnArgument, None] = None, label='', comment=''):
        if not dst:
            dst = PandasmInsnArgument('acc')
        insn = NAddressCode('', [dst, func, *args], NAddressCodeType.CALL, label_name=label, comment=comment)
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
        insn = NAddressCode('', [retval], NAddressCodeType.RETURN, label_name=label)
        self.insert(insn)

    def create_uncond_throw(self, exception: PandasmInsnArgument, label=''):
        # since we don't take exception handlers into account for now,
        # an unconditional throw instruction will mean the end of a basic block and no successors,
        # so split the block from here if there are more instructions after this one,
        # and do not connect to the next block
        # TODO: deal with exception handlers properly
        next_insn_idx = self.insert_point[1] + 1
        if next_insn_idx < len(self.insert_point[0].insns):
            next_insn = self.insert_point[0].insns[next_insn_idx]
            self.insert_point[0].split_block(next_insn, False)

        insn = NAddressCode('', [exception], NAddressCodeType.UNCOND_THROW, label_name=label)
        self.insert(insn)

    def create_cond_throw(self, cond_arg1, cond_arg2, rop, exception: PandasmInsnArgument, label=''):
        # since we don't take exception handlers into account for now,
        # we assume a conditional throw instruction will not go to a handler (i.e., no block split needed)
        # TODO: deal with exception handlers properly
        insn = NAddressCode(rop, [cond_arg1, cond_arg2, exception], NAddressCodeType.COND_THROW, label_name=label)
        self.insert(insn)
