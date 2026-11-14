import unittest

from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import AssignNAC, CallNAC, ReturnNAC
from decompile.passes.live_variable import LiveVariableAnalysis
from decompile.passes.peephole_opt import PeepholeOptimization
from decompile.passes.reaching_def import ReachingDefinitions
from pandasm.insn import PandasmInsnArgument as Arg


class RemainingDataflowFixTests(unittest.TestCase):
    def test_property_folds_keep_handler_visible_write(self):
        for kind in ('self_read', 'read', 'write'):
            for handler_reads in (False, True):
                with self.subTest(kind=kind, handler_reads=handler_reads):
                    method = IRMethod('property_fold')
                    block, handler = IRBlock(method), IRBlock(method)
                    block.add_exception_successor(handler)
                    a, b, c = [Arg('reg', name) for name in ('a', 'b', 'c')]
                    first = AssignNAC('', a, b)
                    member = Arg('field', 'p', a)
                    second = (AssignNAC('', member, c) if kind == 'write' else
                              AssignNAC('', a if kind == 'self_read' else c, member))
                    block.insert_insn(first)
                    block.insert_insn(second)
                    handler.insert_insn(ReturnNAC(a if handler_reads else Arg('undefined')))
                    analysis = LiveVariableAnalysis()
                    _, out_l = analysis.run_on_method(method)

                    PeepholeOptimization(out_l, analysis.exception_live).eliminate_redundant_load_store(block)

                    self.assertEqual(first in block.insns, handler_reads)
                    if handler_reads:
                        self.assertEqual(member.ref_obj, a)
                    else:
                        self.assertEqual(member.ref_obj, b)

    def test_block_tail_copy_keeps_value_needed_by_successor(self):
        for successor_reads in (False, True):
            with self.subTest(successor_reads=successor_reads):
                method = IRMethod('tail_copy')
                block, successor = IRBlock(method), IRBlock(method)
                block.add_successor(successor)
                a, b, c = [Arg('reg', name) for name in ('a', 'b', 'c')]
                first = AssignNAC('', a, b)
                block.insert_insn(first)
                block.insert_insn(AssignNAC('', c, a))
                successor.insert_insn(ReturnNAC(a if successor_reads else c))
                analysis = LiveVariableAnalysis()
                _, out_l = analysis.run_on_method(method)

                PeepholeOptimization(out_l, analysis.exception_live).eliminate_redundant_load_store(block)

                self.assertEqual(first in block.insns, successor_reads)

    def test_operator_is_not_relocated_across_property_access(self):
        method = IRMethod('operator_then_property')
        block = IRBlock(method)
        a, b = Arg('reg', 'a'), Arg('reg', 'b')
        first = AssignNAC('-', a, b)
        second = AssignNAC('', a, Arg('field', 'p', a))
        block.insert_insn(first)
        block.insert_insn(second)
        analysis = LiveVariableAnalysis()
        _, out_l = analysis.run_on_method(method)

        PeepholeOptimization(out_l, analysis.exception_live).eliminate_redundant_load_store(block)

        self.assertEqual(block.insns, [first, second])
        self.assertEqual(second.op, '')

    def test_handler_merges_exception_predecessors_and_normal_entry(self):
        method = IRMethod('reaching_handler')
        entry, left, right, normal, handler = [IRBlock(method) for _ in range(5)]
        for branch in (left, right, normal):
            entry.add_successor(branch)
        normal.add_successor(handler)
        left.add_exception_successor(handler)
        right.add_exception_successor(handler)
        x = Arg('reg', 'x')
        definitions = []
        failures = []
        for index, block in enumerate((left, right)):
            definition = AssignNAC('', x, Arg('imm', str(index)))
            failure = CallNAC(Arg('func', 'fail'), [], x)
            block.insert_insn(definition)
            block.insert_insn(failure)
            definitions.append(definition)
            failures.append(failure)
        normal_definition = AssignNAC('', x, Arg('imm', '2'))
        normal.insert_insn(normal_definition)
        handler.insert_insn(ReturnNAC(x))

        analysis = ReachingDefinitions()
        in_r, _ = analysis.run_on_method(method)

        self.assertEqual(in_r[handler], set(definitions + [normal_definition]))
        self.assertEqual(analysis.exception_in[handler], set(definitions))
        self.assertTrue(all(failure not in in_r[handler] for failure in failures))


if __name__ == '__main__':
    unittest.main()
