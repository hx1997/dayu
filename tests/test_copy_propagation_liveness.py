import unittest

from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.method import IRMethod
from decompile.ir.nac import AssignNAC, CallNAC, ReturnNAC, UncondThrowNAC
from decompile.passes.copy_propagation import CopyPropagation
from decompile.passes.dead_code import DeadCodeElimination
from decompile.passes.live_variable import LiveVariableAnalysis
from decompile.passes.reaching_def import ReachingDefinitions
from pandasm.insn import PandasmInsnArgument as Arg


class CopyPropagationLivenessTests(unittest.TestCase):
    def optimize(self, method):
        in_r, _ = ReachingDefinitions().run_on_method(method)
        CopyPropagation(in_r, constrained=True).run_on_method(method)
        liveness = LiveVariableAnalysis()
        _, out_l = liveness.run_on_method(method)
        DeadCodeElimination(out_l, liveness.exception_live).run_on_method(method)

    def test_definition_still_used_by_return_or_throw_is_preserved(self):
        for terminator in (ReturnNAC, UncondThrowNAC):
            with self.subTest(terminator=terminator.__name__):
                method = IRMethod('remaining_use')
                block = IRBlock(method)
                value = Arg('reg', 'v0')
                definition = AssignNAC(op='', dst=value, src=Arg('imm', '0x1'))
                use = CallNAC(func=Arg('func', 'consume'), call_args=[value], dst=Arg('acc'))
                block.insert_insn(definition)
                block.insert_insn(use)
                block.insert_insn(terminator(value))

                self.optimize(method)

                self.assertEqual(use.call_args, [Arg('imm', '0x1')])
                self.assertIn(definition, block.insns)
                self.assertEqual(block.insns[-1].get_uses(), [value])

    def test_definition_still_used_by_handler_is_preserved(self):
        method = IRMethod('handler_use')
        block, handler = IRBlock(method), IRBlock(method)
        block.add_exception_successor(handler)
        value = Arg('reg', 'v0')
        definition = AssignNAC(op='', dst=value, src=Arg('imm', '0x1'))
        use = CallNAC(func=Arg('func', 'may_fail'), call_args=[value], dst=Arg('acc'))
        block.insert_insn(definition)
        block.insert_insn(use)
        block.insert_insn(ReturnNAC(Arg('undefined')))
        handler.insert_insn(ReturnNAC(value))

        self.optimize(method)

        self.assertEqual(use.call_args, [Arg('imm', '0x1')])
        self.assertIn(definition, block.insns)
        self.assertEqual(handler.insns[0].get_uses(), [value])

    def test_self_referencing_rhs_is_not_expanded_locally_or_across_blocks(self):
        value = Arg('reg', 'x')
        cases = [
            ('increment', '+', value, Arg('imm', '0x1')),
            ('prefix', '+', Arg('str', 'prefix'), value),
            ('nested', '', ExprArg([value, Arg('imm', '0x1')], 'arith', '+'), None),
            ('property', '', Arg('field', 'p', value), None),
        ]
        for name, op, src, src2 in cases:
            for across_blocks in (False, True):
                with self.subTest(rhs=name, across_blocks=across_blocks):
                    method = IRMethod(name)
                    block = IRBlock(method)
                    block.insert_insn(AssignNAC(op=op, dst=value, src=src, src2=src2))
                    use_block = IRBlock(method) if across_blocks else block
                    if across_blocks:
                        block.add_successor(use_block)
                    use = CallNAC(func=Arg('func', 'consume'), call_args=[value], dst=Arg('acc'))
                    use_block.insert_insn(use)
                    use_block.insert_insn(ReturnNAC(Arg('undefined')))

                    CopyPropagation({}, constrained=False).run_on_method(method)

                    self.assertEqual(use.call_args, [value])

    def test_property_read_is_not_repeated_through_result_copies(self):
        for nested in (False, True):
            for across_blocks in (False, True):
                with self.subTest(nested=nested, across_blocks=across_blocks):
                    method = IRMethod('property_read')
                    block = IRBlock(method)
                    x, y, obj = Arg('reg', 'x'), Arg('reg', 'y'), Arg('reg', 'obj')
                    source = Arg('field', 'p', obj)
                    if nested:
                        source = ExprArg([ExprArg([source, Arg('imm', '0x1')], 'arith', '+'),
                                          Arg('imm', '0x2')], 'arith', '*')
                    read = AssignNAC(op='', dst=x, src=source)
                    block.insert_insn(read)
                    use_block = IRBlock(method) if across_blocks else block
                    if across_blocks:
                        block.add_successor(use_block)
                    use_block.insert_insn(AssignNAC(op='', dst=y, src=x))
                    uses = [CallNAC(func=Arg('func', 'consume'), call_args=[y], dst=Arg('acc'))
                            for _ in range(2)]
                    for use in uses:
                        use_block.insert_insn(use)
                    use_block.insert_insn(ReturnNAC(Arg('undefined')))

                    CopyPropagation({}, constrained=False).run_on_method(method)
                    liveness = LiveVariableAnalysis()
                    _, out_l = liveness.run_on_method(method)
                    DeadCodeElimination(out_l, liveness.exception_live).run_on_method(method)

                    self.assertIn(read, block.insns)
                    self.assertTrue(all(use.call_args == [x] for use in uses))
                    self.assertEqual(sum(insn.type == read.type
                                         for b in method.blocks for insn in b.insns), 1)

    def test_property_write_to_copy_source_still_kills_the_copy(self):
        method = IRMethod('property_read_kills_copy')
        block = IRBlock(method)
        x, y = Arg('reg', 'x'), Arg('reg', 'y')
        block.insert_insn(AssignNAC(op='', dst=x, src=y))
        block.insert_insn(AssignNAC(op='', dst=y, src=Arg('field', 'p', Arg('reg', 'obj'))))
        use = CallNAC(func=Arg('func', 'consume'), call_args=[x], dst=Arg('acc'))
        block.insert_insn(use)

        CopyPropagation({}, constrained=False).run_on_method(method)

        self.assertEqual(use.call_args, [x])

    def test_rejected_self_update_still_kills_an_older_copy(self):
        method = IRMethod('kill_old_copy')
        block = IRBlock(method)
        x, y = Arg('reg', 'x'), Arg('reg', 'y')
        block.insert_insn(AssignNAC(op='', dst=x, src=y))
        block.insert_insn(AssignNAC(op='+', dst=y, src=y, src2=Arg('imm', '0x1')))
        use = CallNAC(func=Arg('func', 'consume'), call_args=[x], dst=Arg('acc'))
        block.insert_insn(use)

        CopyPropagation({}, constrained=False).run_on_method(method)

        self.assertEqual(use.call_args, [x])

    def test_potentially_throwing_operations_are_evaluated_once(self):
        for op in ('+', '/', '<'):
            for nested in (False, True):
                for across_blocks in (False, True):
                    with self.subTest(op=op, nested=nested, across_blocks=across_blocks):
                        method = IRMethod('operation_copy')
                        block = IRBlock(method)
                        x, y, obj = Arg('reg', 'x'), Arg('reg', 'y'), Arg('reg', 'obj')
                        one = Arg('imm', '0x1')
                        operation = (AssignNAC(op='', dst=x, src=ExprArg([obj, one], 'arith', op))
                                     if nested else AssignNAC(op=op, dst=x, src=obj, src2=one))
                        block.insert_insn(operation)
                        use_block = IRBlock(method) if across_blocks else block
                        if across_blocks:
                            block.add_successor(use_block)
                        use_block.insert_insn(AssignNAC(op='', dst=y, src=x))
                        uses = [CallNAC(func=Arg('func', 'consume'), call_args=[y], dst=Arg('acc'))
                                for _ in range(2)]
                        for use in uses:
                            use_block.insert_insn(use)
                        use_block.insert_insn(ReturnNAC(Arg('undefined')))

                        CopyPropagation({}, constrained=False).run_on_method(method)
                        liveness = LiveVariableAnalysis()
                        _, out_l = liveness.run_on_method(method)
                        DeadCodeElimination(out_l, liveness.exception_live).run_on_method(method)

                        self.assertIn(operation, block.insns)
                        self.assertTrue(all(use.call_args == [x] for use in uses))
                        self.assertEqual(sum(insn.type == operation.type
                                             for b in method.blocks for insn in b.insns), 1)

    def test_dce_removes_definition_when_all_uses_are_replaced(self):
        method = IRMethod('fully_replaced')
        block = IRBlock(method)
        value = Arg('reg', 'v0')
        definition = AssignNAC(op='', dst=value, src=Arg('imm', '0x1'))
        use = CallNAC(func=Arg('func', 'consume'), call_args=[value], dst=Arg('acc'))
        block.insert_insn(definition)
        block.insert_insn(use)
        block.insert_insn(ReturnNAC(Arg('undefined')))

        in_r, _ = ReachingDefinitions().run_on_method(method)
        CopyPropagation(in_r, constrained=True).run_on_method(method)
        self.assertIn(definition, block.insns)
        self.assertEqual(use.call_args, [Arg('imm', '0x1')])

        liveness = LiveVariableAnalysis()
        _, out_l = liveness.run_on_method(method)
        DeadCodeElimination(out_l, liveness.exception_live).run_on_method(method)
        self.assertNotIn(definition, block.insns)


if __name__ == '__main__':
    unittest.main()
