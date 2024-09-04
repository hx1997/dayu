import typing

from decompile.ir.nac import NAddressCode, NAddressCodeType
from pandasm.insn import PandasmInsnArgument


class IRBlock:
    def __init__(self, parent_method=None):
        self.insns: typing.List[NAddressCode] = []
        self.parent_method = parent_method
        if self.parent_method:
            self.parent_method.insert_block(self)

        self.predecessors: typing.List[IRBlock] = []
        self.successors: typing.List[IRBlock] = []
        self.label2insn_map: typing.Dict[str, typing.Union[NAddressCode, None]] = {}
        self.defs = set()  # populated by the DefUseAnalysis pass
        self.uses = set()  # populated by the DefUseAnalysis pass

    def insert_insn(self, insn: NAddressCode, at=None):
        """
        Insert an instruction
        Warning: this method doesn't maintain the CFG.
        Use higher level methods in IRBuilder if you want to keep CFG updated
        """
        if at is not None:
            self.insns.insert(at, insn)
        else:
            self.insns.append(insn)
        insn.parent_block = self
        if insn.label:
            self.label2insn_map[insn.label] = insn

    def remove_insn(self, insn: NAddressCode):
        """
        Remove an instruction
        Warning: this method doesn't maintain the CFG.
        Use higher level methods in IRBuilder if you want to keep CFG updated
        """
        at = self.insns.index(insn)
        self.remove_insn_at(at)

    def clear_insns(self):
        self.insns.clear()

    def remove_insn_at(self, at):
        if at == 0:
            # if the instruction to be removed is the first in block, move its label (if any) to the next instruction
            label = self.insns[at].label
            if label and len(self.insns) > 1:
                self.insns[1].label = label
                self.label2insn_map[label] = self.insns[1]
        else:
            label = self.insns[at].label
            if label:
                del self.label2insn_map[label]

        # if the instruction to be removed is control-flow-related, i.e. a jump, return, or a throw,
        # cut edges in the CFG accordingly
        # TODO: handle jumps and COND_THROWs
        if self.insns[at].type in [NAddressCodeType.UNCOND_THROW, NAddressCodeType.RETURN]:
            self.clear_successors()

        del self.insns[at]

    def erase_from_parent(self):
        if not self.parent_method:
            raise Exception(f'{self.__class__.__name__}: this block has no parent')
        self.parent_method.remove_block(self)

    def split_block(self, insn: NAddressCode, connect=True, extra_predecessors=None):
        """
        Split this block at the specified instruction and return the new block
        If `connect` is True, then:
            (1) the new block will be a successor to this block, and this block will be a predecessor to the new block;
            (2) each block in `extra_predecessors` will be added as a predecessor to the new block,
            and the new block will be a successor to it
        """
        split_point = self.insns.index(insn)
        if split_point == 0:
            # splitting at the first instruction doesn't actually do anything, so there's no new block,
            # but it's important to maintain the predecessor and successor relationships of this block
            # since the split could come from two different predecessors, for example in the case where
            # two blocks jump to the same block, when one block has already split at the branch target,
            # the other shouldn't split at the same target again when it calls this method, but it should
            # be added as a predecessor to the branch target block
            if connect and extra_predecessors:
                for predecessor in extra_predecessors:
                    self.add_predecessor(predecessor)
            return None

        # create a new block and copy the instructions starting from the split point until the end of block
        new_block = IRBlock(self.parent_method)
        for _ in range(split_point, len(self.insns)):
            new_block.insert_insn(self.insns[split_point])
            self.remove_insn_at(split_point)

        # update predecessors and successors
        if connect:
            for succ in self.successors.copy():
                succ.remove_predecessor(self)
                succ.add_predecessor(new_block)

            self.add_successor(new_block)
            if extra_predecessors:
                for predecessor in extra_predecessors:
                    new_block.add_predecessor(predecessor)

        return new_block

    def get_insn_by_label(self, label) -> typing.Union[NAddressCode, None]:
        if isinstance(label, PandasmInsnArgument):
            label = str(label).replace('label:', '')
        return self.label2insn_map.get(label, None)

    def add_predecessor(self, predecessor):
        """
        Add a predecessor to this block, and add this block as a successor to it
        """
        if predecessor not in self.predecessors:
            self.predecessors.append(predecessor)
        if self not in predecessor.successors:
            predecessor.add_successor(self)

    def add_successor(self, successor):
        """
        Add a successor to this block, and add this block as a predecessor to it
        """
        if successor not in self.successors:
            self.successors.append(successor)
        if self not in successor.predecessors:
            successor.add_predecessor(self)

    def remove_predecessor(self, predecessor):
        if predecessor in self.predecessors:
            self.predecessors.remove(predecessor)
        if self in predecessor.successors:
            predecessor.successors.remove(self)

    def remove_successor(self, successor):
        if successor in self.successors:
            self.successors.remove(successor)
        if self in successor.predecessors:
            successor.predecessors.remove(self)

    def clear_predecessors(self):
        for pred in self.predecessors.copy():
            self.remove_predecessor(pred)

    def clear_successors(self):
        for succ in self.successors.copy():
            self.remove_successor(succ)
