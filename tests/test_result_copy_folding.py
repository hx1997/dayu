import unittest

from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.method import IRMethod
from decompile.ir.nac import AssignNAC, CallNAC, ReturnNAC
from decompile.ir.exception_semantics import may_throw
from decompile.passes.copy_propagation import CopyPropagation
from decompile.passes.live_variable import LiveVariableAnalysis
from decompile.passes.dead_code import DeadCodeElimination
from decompile.passes.peephole_opt import PeepholeOptimization
from pandasm.insn import PandasmInsnArgument as Arg


class ResultCopyFoldingTests(unittest.TestCase):
    def fold(self, method):
        analysis = LiveVariableAnalysis()
        _, out_l = analysis.run_on_method(method)
        PeepholeOptimization(out_l, analysis.exception_live).fold_result_copy(method.blocks[0])

    def test_callee_read_moves_once_and_keeps_explicit_arguments(self):
        method = IRMethod('callee_read')
        block = IRBlock(method)
        temp, obj = Arg('reg', 't'), Arg('reg', 'obj')
        member = Arg('field', 'method', obj)
        block.insert_insn(AssignNAC('', temp, member))
        arguments = [Arg('FunctionObject'), Arg('NewTarget'), obj, Arg('str', 'message')]
        call = CallNAC(temp, arguments, Arg('acc'))
        block.insert_insn(call)
        block.insert_insn(ReturnNAC(Arg('acc')))
        analysis = LiveVariableAnalysis()
        _, out_l = analysis.run_on_method(method)

        PeepholeOptimization(out_l, analysis.exception_live).fold_single_use(block)

        self.assertEqual(len(block.insns), 2)
        self.assertEqual(call.func, member)
        self.assertEqual(call.call_args, arguments)

    def test_single_use_moves_once_and_preserves_evaluation_order(self):
        for mode in ('call', 'ark_call', 'return', 'self_update', 'twice', 'earlier_getter',
                     'later_use', 'handler', 'short_circuit'):
            with self.subTest(mode=mode):
                method = IRMethod(mode)
                block = IRBlock(method)
                temp, obj = Arg('reg', 't'), Arg('reg', 'obj')
                calculation = AssignNAC('+', temp, obj, Arg('imm', '0x1'))
                block.insert_insn(calculation)
                if mode == 'return':
                    use = ReturnNAC(temp)
                elif mode == 'self_update':
                    use = AssignNAC('+', temp, temp, Arg('str', 'suffix'))
                elif mode == 'short_circuit':
                    use = AssignNAC('&&', Arg('reg', 'x'), Arg('reg', 'flag'), temp)
                else:
                    args = [temp, temp] if mode == 'twice' else [Arg('str', 'prefix'), temp]
                    if mode == 'ark_call':
                        args = [Arg('FunctionObject'), Arg('NewTarget'), Arg('module', 'hilog'),
                                Arg('imm', '0x0'), Arg('str', 'hello'), temp]
                    if mode == 'earlier_getter':
                        args[0] = Arg('field', 'p', obj)
                    use = CallNAC(Arg('reg', 'fn'), args, Arg('acc'))
                block.insert_insn(use)
                if mode == 'later_use':
                    block.insert_insn(ReturnNAC(temp))
                if mode == 'self_update':
                    block.insert_insn(ReturnNAC(temp))
                if mode == 'handler':
                    handler = IRBlock(method)
                    block.add_exception_successor(handler)
                    handler.insert_insn(ReturnNAC(temp))
                analysis = LiveVariableAnalysis()
                _, out_l = analysis.run_on_method(method)

                PeepholeOptimization(out_l, analysis.exception_live).fold_single_use(block)

                if mode in ('call', 'ark_call', 'return', 'self_update'):
                    self.assertNotIn(calculation, block.insns)
                    self.assertEqual(str(use).count('obj + 0x1'), 1)
                else:
                    self.assertIn(calculation, block.insns)

    def test_single_use_preserves_entry_label(self):
        method = IRMethod('entry_label')
        block = IRBlock(method)
        temp = Arg('reg', 't')
        block.insert_insn(AssignNAC('+', temp, Arg('reg', 'obj'), Arg('imm', '0x1'),
                                   label_name='entry'))
        use = ReturnNAC(temp)
        block.insert_insn(use)
        analysis = LiveVariableAnalysis()
        _, out_l = analysis.run_on_method(method)

        PeepholeOptimization(out_l, analysis.exception_live).fold_single_use(block)

        self.assertEqual(block.insns, [use])
        self.assertIn('entry', use.label_aliases)

    def test_throwing_computation_is_moved_once(self):
        method = IRMethod('move_result')
        block = IRBlock(method)
        temp, target = Arg('reg', 't'), Arg('reg', 'x')
        calculation = AssignNAC('+', temp, Arg('reg', 'obj'), Arg('imm', '0x1'))
        block.insert_insn(calculation)
        block.insert_insn(AssignNAC('', target, temp))
        block.insert_insn(ReturnNAC(target))

        self.fold(method)

        self.assertEqual(block.insns, [calculation, block.insns[-1]])
        self.assertEqual(calculation.dst, target)
        self.assertTrue(may_throw(calculation))

    def test_normal_successor_use_prevents_moving(self):
        method = IRMethod('normal_use')
        block, successor = IRBlock(method), IRBlock(method)
        block.add_successor(successor)
        temp = Arg('reg', 't')
        calculation = AssignNAC('+', temp, Arg('reg', 'obj'), Arg('imm', '0x1'))
        block.insert_insn(calculation)
        block.insert_insn(AssignNAC('', Arg('reg', 'x'), temp))
        successor.insert_insn(ReturnNAC(temp))

        self.fold(method)

        self.assertEqual(len(block.insns), 2)
        self.assertEqual(calculation.dst, temp)

    def test_handler_use_keeps_completed_result(self):
        method = IRMethod('handler_use')
        block, handler = IRBlock(method), IRBlock(method)
        block.add_exception_successor(handler)
        temp = Arg('reg', 't')
        calculation = AssignNAC('+', temp, Arg('reg', 'obj'), Arg('imm', '0x1'))
        block.insert_insn(calculation)
        block.insert_insn(AssignNAC('', Arg('reg', 'x'), temp))
        block.insert_insn(CallNAC(Arg('func', 'fail'), [], Arg('acc')))
        handler.insert_insn(ReturnNAC(temp))

        self.fold(method)

        self.assertEqual(calculation.dst, temp)
        self.assertEqual(len(block.insns), 3)

    def test_throw_keeps_old_target_visible_to_handler(self):
        method = IRMethod('old_target')
        block, handler = IRBlock(method), IRBlock(method)
        block.add_exception_successor(handler)
        temp, target = Arg('reg', 't'), Arg('reg', 'x')
        original = AssignNAC('', target, Arg('imm', '0x7'))
        calculation = AssignNAC('+', temp, Arg('reg', 'obj'), Arg('imm', '0x1'))
        block.insert_insn(original)
        block.insert_insn(calculation)
        block.insert_insn(AssignNAC('', target, temp))
        block.insert_insn(ReturnNAC(target))
        handler.insert_insn(ReturnNAC(target))

        self.fold(method)
        analysis = LiveVariableAnalysis()
        _, out_l = analysis.run_on_method(method)
        DeadCodeElimination(out_l, analysis.exception_live).run_on_method(method)

        self.assertIn(original, block.insns)
        self.assertEqual(calculation.dst, target)
        self.assertEqual(len(block.insns), 3)

    def test_labelled_copy_is_not_moved(self):
        method = IRMethod('labelled_copy')
        block = IRBlock(method)
        temp = Arg('reg', 't')
        block.insert_insn(AssignNAC('+', temp, Arg('reg', 'obj'), Arg('imm', '0x1')))
        block.insert_insn(AssignNAC('', Arg('reg', 'x'), temp, label_name='entry'))

        self.fold(method)

        self.assertEqual(len(block.insns), 2)

    def test_safe_operators_propagate_and_original_is_removed(self):
        for op in ('!', '===', '!=='):
            for nested in (False, True):
                with self.subTest(op=op, nested=nested):
                    method = IRMethod('safe_operator')
                    block = IRBlock(method)
                    temp = Arg('reg', 't')
                    operands = [Arg('reg', 'a')]
                    if op != '!':
                        operands.append(Arg('reg', 'b'))
                    calculation = (AssignNAC('', temp, ExprArg(operands, 'arith', op)) if nested
                                   else AssignNAC(op, temp, operands[0], operands[1] if len(operands) == 2 else None))
                    block.insert_insn(calculation)
                    use = CallNAC(Arg('func', 'consume'), [temp], Arg('acc'))
                    block.insert_insn(use)
                    block.insert_insn(ReturnNAC(Arg('undefined')))

                    CopyPropagation({}, constrained=False).run_on_method(method)
                    analysis = LiveVariableAnalysis()
                    _, out_l = analysis.run_on_method(method)
                    DeadCodeElimination(out_l, analysis.exception_live).run_on_method(method)

                    self.assertIsInstance(use.call_args[0], ExprArg)
                    self.assertNotIn(calculation, block.insns)

    def test_safe_operator_does_not_hide_property_read(self):
        calculation = AssignNAC('!', Arg('reg', 't'), Arg('field', 'p', Arg('reg', 'obj')))
        self.assertTrue(may_throw(calculation))


if __name__ == '__main__':
    unittest.main()
