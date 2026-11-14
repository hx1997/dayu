import unittest

from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import AssignNAC, CallNAC, ReturnNAC
from decompile.passes.dead_code import DeadCodeElimination
from decompile.passes.live_variable import LiveVariableAnalysis
from pandasm.insn import PandasmInsnArgument as Arg


def assign(dst, value):
    return AssignNAC(op='', dst=dst, src=Arg('imm', value))


def call(dst=None):
    return CallNAC(func=Arg('func', 'may_fail'), call_args=[], dst=dst or Arg('acc'))


class ExceptionLivenessTests(unittest.TestCase):
    def test_handler_observes_definition_before_throwing_instruction(self):
        method = IRMethod('instruction_state')
        block = IRBlock(method)
        handler = IRBlock(method)
        block.add_exception_successor(handler)
        value = Arg('reg', 'v0')
        before = assign(value, '0x1')
        after = assign(value, '0x2')
        for insn in [before, call(), after, ReturnNAC(Arg('undefined'))]:
            block.insert_insn(insn)
        handler.insert_insn(ReturnNAC(value))
        analysis = LiveVariableAnalysis()
        in_l, out_l = analysis.run_on_method(method)

        self.assertEqual(out_l[block], set())
        self.assertNotIn(value, in_l[block])
        self.assertEqual(analysis.exception_live[block], {value})
        DeadCodeElimination(out_l, analysis.exception_live).run_on_method(method)
        self.assertIn(before, block.insns)
        self.assertNotIn(after, block.insns)

    def test_throwing_write_preserves_previous_destination_for_handler(self):
        method = IRMethod('failing_destination')
        block = IRBlock(method)
        handler = IRBlock(method)
        block.add_exception_successor(handler)
        value = Arg('reg', 'v0')
        previous = assign(value, '0x1')
        block.insert_insn(previous)
        block.insert_insn(call(value))
        block.insert_insn(ReturnNAC(Arg('undefined')))
        handler.insert_insn(ReturnNAC(value))
        analysis = LiveVariableAnalysis()
        _, out_l = analysis.run_on_method(method)

        DeadCodeElimination(out_l, analysis.exception_live).run_on_method(method)
        self.assertIn(previous, block.insns)

    def test_handler_acc_does_not_keep_old_acc_assignment(self):
        method = IRMethod('handler_acc')
        block = IRBlock(method)
        handler = IRBlock(method)
        block.add_exception_successor(handler)
        previous = assign(Arg('acc'), '0x1')
        block.insert_insn(previous)
        block.insert_insn(call())
        block.insert_insn(ReturnNAC(Arg('undefined')))
        handler.insert_insn(ReturnNAC(Arg('acc')))
        analysis = LiveVariableAnalysis()
        _, out_l = analysis.run_on_method(method)

        self.assertEqual(analysis.exception_live[block], set())
        DeadCodeElimination(out_l, analysis.exception_live).run_on_method(method)
        self.assertNotIn(previous, block.insns)

    def test_nested_handler_requirements_reach_fixed_point_without_cfg_mutation(self):
        method = IRMethod('nested_handlers')
        block, inner, outer = [IRBlock(method) for _ in range(3)]
        block.add_exception_successor(inner)
        inner.add_exception_successor(outer)
        block.insert_insn(call())
        inner.insert_insn(call())
        value = Arg('reg', 'v0')
        outer.insert_insn(ReturnNAC(value))
        normal_edges = [(b.predecessors.copy(), b.successors.copy()) for b in method.blocks]
        analysis = LiveVariableAnalysis()
        in_l, out_l = analysis.run_on_method(method)

        self.assertIn(value, in_l[block])
        self.assertIn(value, analysis.exception_live[inner])
        self.assertEqual(out_l[block], set())
        self.assertEqual(normal_edges, [(b.predecessors, b.successors) for b in method.blocks])

    def test_dead_property_read_is_retained_because_it_can_throw(self):
        method = IRMethod('property_read')
        block = IRBlock(method)
        read = AssignNAC(op='', dst=Arg('reg', 'v0'),
                         src=Arg('field', 'property', Arg('reg', 'v1')))
        block.insert_insn(read)
        block.insert_insn(ReturnNAC(Arg('undefined')))

        DeadCodeElimination({block: set()}).run_on_method(method)
        self.assertIn(read, block.insns)

    def test_empty_handler_entry_is_preserved(self):
        method = IRMethod('empty_handler')
        block, handler, continuation = [IRBlock(method) for _ in range(3)]
        block.add_exception_successor(handler)
        handler.add_successor(continuation)
        handler.insert_insn(assign(Arg('reg', 'v0'), '0x1'))

        DeadCodeElimination({handler: set()}).analyze_block(handler)
        self.assertEqual(handler.insns, [])
        self.assertIn(handler, method.blocks)
        self.assertEqual(block.exception_successors, [handler])
        self.assertEqual(handler.successors, [continuation])

    def test_analysis_only_does_not_remove_empty_block(self):
        method = IRMethod('read_only_query')
        block, empty, continuation = [IRBlock(method) for _ in range(3)]
        block.add_successor(empty)
        empty.add_successor(continuation)

        DeadCodeElimination({empty: set()}).analyze_block(empty, False)
        self.assertEqual(method.blocks, [block, empty, continuation])
        self.assertEqual(block.successors, [empty])
        self.assertEqual(empty.successors, [continuation])


if __name__ == '__main__':
    unittest.main()
