import typing
from dataclasses import dataclass

from decompile.ir.basicblock import IRBlock
from decompile.ir.method_ctx import IRMethodContext
from decompile.ir.nac import NAddressCode
from pandasm.insn import PandasmInsnArgument
from pandasm.method import PandasmTryCatchRegion


@dataclass
class ResolvedTryRegion:
    # region preserves the original Pandasm exception-table entry, while the
    # block-id sets identify bodies; None means the handler extent is unknown.
    region: PandasmTryCatchRegion
    try_block_ids: typing.Set[int]
    handler_block_ids: typing.Set[int] | None
    handler_entry_id: int | None = None
    continuation_label: str | None = None


class IRMethod:
    def __init__(self, name=None, parent_class=None):
        self.name = name
        self.blocks: typing.List[IRBlock] = []
        # Raw .catchall metadata copied from Pandasm parsing.
        self.try_regions: typing.List[PandasmTryCatchRegion] = []
        # IR-level resolution of try_regions onto the CFG blocks built for this method.
        self.resolved_try_regions: typing.List[ResolvedTryRegion] = []
        self.handler_extent_unknown = False
        self.parent_class = parent_class
        if self.parent_class:
            self.parent_class.insert_method(self)
        self.ctx = IRMethodContext(self)

    def insert_block(self, block: IRBlock):
        self.blocks.append(block)

    def remove_block(self, block: IRBlock):
        for predecessor in block.exception_predecessors.copy():
            block.remove_exception_predecessor(predecessor)
        for successor in block.exception_successors.copy():
            block.remove_exception_successor(successor)
        self.blocks.remove(block)

    def rebuild_exception_edges(self):
        """Rebuild catchall edges from resolved lexical regions.

        Normal predecessors/successors remain untouched. Origin ids allow this
        relation to survive block-preserving IR passes.
        """
        for block in self.blocks:
            block.clear_exception_predecessors()
            block.clear_exception_successors()

        for resolved in self.resolved_try_regions:
            try_blocks = {
                block for block in self.blocks
                if block.origin_block_ids.intersection(resolved.try_block_ids)
            }
            entry_id = resolved.handler_entry_id
            # Older pass callers may supply an explicit range without an entry id.
            if entry_id is None and resolved.handler_block_ids:
                entry_id = min(resolved.handler_block_ids)
            handler_blocks = [block for block in self.blocks if entry_id in block.origin_block_ids]
            if not try_blocks or not handler_blocks:
                continue
            # The current PandasmTryCatchRegion represents one catchall range,
            # so its handler range has one entry block. Keep the loop explicit
            # for nested/reduced origin sets and future multiple-handler entries.
            handler = handler_blocks[0]
            for block in try_blocks:
                if block is not handler:
                    block.add_exception_successor(handler)

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
