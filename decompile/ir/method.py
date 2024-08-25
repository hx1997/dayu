import typing

from decompile.ir.basicblock import IRBlock
from decompile.ir.nac import NAddressCode
from pandasm.insn import PandasmInsnArgument


class IRMethod:
    def __init__(self, name=None, parent_class=None):
        self.name = name
        self.blocks: typing.List[IRBlock] = []
        self.parent_class = parent_class
        if self.parent_class:
            self.parent_class.insert_method(self)

    def insert_block(self, block: IRBlock):
        self.blocks.append(block)

    def remove_block(self, block: IRBlock):
        self.blocks.remove(block)

    def erase_from_parent(self):
        if not self.parent_class:
            raise Exception(f'{self.__class__.__name__}: this method has no parent')
        self.parent_class.remove_method(self)

    def get_insn_by_label(self, label) -> typing.Union[NAddressCode, None]:
        for block in self.blocks:
            if isinstance(label, PandasmInsnArgument):
                label = str(label).replace('label:', '')
            insn = block.get_insn_by_label(label)
            if insn:
                return insn
        return None

    def count_insns(self):
        return sum([len(block.insns) for block in self.blocks])
