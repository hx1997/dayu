import unittest

from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import AssignNAC, ReturnNAC
from decompile.ir.exception_semantics import may_throw
from decompile.passes.dead_code import DeadCodeElimination
from decompile.passes.live_variable import LiveVariableAnalysis
from decompile.passes.peephole_opt import PeepholeOptimization
from pandasm.insn import PandasmInsnArgument as Arg


class PotentiallyThrowingOperationsTests(unittest.TestCase):
    def property_read(self):
        return AssignNAC('', Arg('reg', 'value'),
                         Arg('field', 'property', Arg('reg', 'object')))

    def test_property_access_is_opt_in_for_analysis(self):
        read = self.property_read()
        self.assertFalse(may_throw(read, set()))
        self.assertTrue(may_throw(read, {'property_access'}))

    def test_default_config_does_not_mark_property_access_throwing(self):
        from decompile.config import DecompilerConfig
        self.assertEqual(DecompilerConfig().potentially_throwing_operations, set())

    def test_property_access_mode_preserves_dead_read(self):
        read = self.property_read()
        block = IRBlock(IRMethod('property_mode'))
        block.insert_insn(read)
        block.insert_insn(ReturnNAC(Arg('undefined')))
        analysis = LiveVariableAnalysis(set())
        _, out_l = analysis.run_on_method(block.parent_method)
        DeadCodeElimination(out_l, analysis.exception_live, set()).run_on_method(block.parent_method)
        self.assertNotIn(read, block.insns)

        read = self.property_read()
        block = IRBlock(IRMethod('property_mode_enabled'))
        block.insert_insn(read)
        block.insert_insn(ReturnNAC(Arg('undefined')))
        analysis = LiveVariableAnalysis({'property_access'})
        _, out_l = analysis.run_on_method(block.parent_method)
        DeadCodeElimination(out_l, analysis.exception_live, {'property_access'}).run_on_method(block.parent_method)
        self.assertIn(read, block.insns)

    def test_property_mode_blocks_single_use_move(self):
        method = IRMethod('property_single_use_mode')
        block = IRBlock(method)
        temp = Arg('reg', 'temp')
        read = AssignNAC('', temp, Arg('field', 'property', Arg('reg', 'object')))
        use = AssignNAC('', Arg('reg', 'result'), temp)
        block.insert_insn(read)
        block.insert_insn(use)
        block.insert_insn(ReturnNAC(Arg('reg', 'result')))
        analysis = LiveVariableAnalysis({'property_access'})
        _, out_l = analysis.run_on_method(method)

        PeepholeOptimization(
            out_l, analysis.exception_live,
            potentially_throwing_operations={'property_access'}).run_on_method(method)

        self.assertIn(read, block.insns)

    def test_property_mode_blocks_old_value_fold(self):
        method = IRMethod('property_fold_mode')
        block = IRBlock(method)
        a, b = Arg('reg', 'a'), Arg('reg', 'b')
        first = AssignNAC('', a, b)
        second = AssignNAC('', a, Arg('field', 'property', a))
        block.insert_insn(first)
        block.insert_insn(second)
        analysis = LiveVariableAnalysis({'property_access'})
        _, out_l = analysis.run_on_method(method)
        PeepholeOptimization(out_l, analysis.exception_live, potentially_throwing_operations={'property_access'}).run_on_method(method)
        self.assertIn(first, block.insns)


if __name__ == '__main__':
    unittest.main()
