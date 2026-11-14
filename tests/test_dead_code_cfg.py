import unittest

from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import AssignNAC, ReturnNAC
from decompile.passes.dead_code import DeadCodeElimination
from pandasm.insn import PandasmInsnArgument


class DeadCodeCFGTests(unittest.TestCase):
    def test_empty_block_preserves_predecessors_successor_and_label(self):
        method = IRMethod('empty_block')
        first = IRBlock(method)
        second = IRBlock(method)
        empty = IRBlock(method)
        continuation = IRBlock(method)
        first.add_successor(empty)
        second.add_successor(empty)
        empty.add_successor(continuation)
        empty.insert_insn(AssignNAC(
            op='', dst=PandasmInsnArgument('reg', 'v0'),
            src=PandasmInsnArgument('acc'), label_name='jump_label_15'))
        continuation.insert_insn(ReturnNAC(retval=PandasmInsnArgument('undefined')))

        DeadCodeElimination({empty: set()}).analyze_block(empty)

        self.assertNotIn(empty, method.blocks)
        self.assertEqual(first.successors, [continuation])
        self.assertEqual(second.successors, [continuation])
        self.assertEqual(set(continuation.predecessors), {first, second})
        self.assertIs(method.get_insn_by_label('jump_label_15'), continuation.insns[0])

    def test_consecutive_empty_blocks_are_processed_in_one_pass(self):
        method = IRMethod('consecutive_empty_blocks')
        first = IRBlock(method)
        second = IRBlock(method)
        continuation = IRBlock(method)
        first.add_successor(second)
        second.add_successor(continuation)
        continuation.insert_insn(ReturnNAC(retval=PandasmInsnArgument('undefined')))

        DeadCodeElimination({b: set() for b in method.blocks}).run_on_method(method)

        self.assertEqual(method.blocks, [continuation])
        self.assertEqual(continuation.predecessors, [])


if __name__ == '__main__':
    unittest.main()
