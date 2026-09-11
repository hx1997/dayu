import unittest

from decompile.ir.basicblock import IRBlock
from decompile.ir.nac import AssignNAC, CallNAC, CondJumpNAC, ImportNAC, NAddressCodeType, ReturnNAC, UnknownNAC
from pandasm.insn import PandasmInsnArgument


class NAddressCodeFormattingTests(unittest.TestCase):
    def test_assign_binary_format(self):
        insn = AssignNAC(
            '+',
            PandasmInsnArgument('reg', 'v0'),
            PandasmInsnArgument('reg', 'v1'),
            PandasmInsnArgument('imm', '1'),
        )

        self.assertEqual(str(insn), 'v0 = v1 + 1')

    def test_assign_unary_or_copy_format(self):
        insn = AssignNAC(
            '',
            PandasmInsnArgument('reg', 'v0'),
            PandasmInsnArgument('reg', 'v1'),
        )

        self.assertEqual(str(insn), 'v0 = v1')

    def test_conditional_jump_two_argument_format(self):
        insn = CondJumpNAC(
            '',
            PandasmInsnArgument('reg', 'v0'),
            PandasmInsnArgument('label', 'jump_label_0'),
        )

        self.assertEqual(str(insn), 'if (v0) jump jump_label_0')

    def test_call_format(self):
        insn = CallNAC(
            PandasmInsnArgument('func', 'foo'),
            [PandasmInsnArgument('reg', 'v1'), PandasmInsnArgument('imm', '2')],
            dst=PandasmInsnArgument('reg', 'v0'),
        )

        self.assertEqual(str(insn), 'v0 = foo(v1, 2)')

    def test_import_format(self):
        insn = ImportNAC(
            PandasmInsnArgument('func', 'default'),
            PandasmInsnArgument('local', 'hilog'),
            '@ohos:hilog',
        )

        self.assertEqual(str(insn), "import { default } as hilog from '@ohos:hilog';")

    def test_label_and_comment_wrapping(self):
        insn = ReturnNAC(
            PandasmInsnArgument('reg', 'v0'),
            label_name='jump_label_0',
            comment='done',
        )

        self.assertEqual(str(insn), 'jump_label_0:\nreturn v0  /* done */')

    def test_assign_single_arg_is_copy_form(self):
        # AssignNAC with only dst+src (no src2) formats as a copy/unary expression
        insn = AssignNAC(
            '',
            PandasmInsnArgument('reg', 'v0'),
            PandasmInsnArgument('reg', 'v1'),
        )
        self.assertEqual(str(insn), 'v0 = v1')

    def test_return_single_arg(self):
        insn = ReturnNAC(
            PandasmInsnArgument('reg', 'v0'),
        )
        self.assertEqual(str(insn), 'return v0')

    def test_removing_first_instruction_preserves_all_labels(self):
        block = IRBlock()
        removed = UnknownNAC('removed', [], label_name='primary')
        removed.label_aliases = ['alias_0', 'alias_1']
        block.insert_insn(removed)
        remaining = UnknownNAC('remaining', [], label_name='existing')
        block.insert_insn(remaining)

        block.remove_insn(removed)

        self.assertEqual(remaining.label, 'existing')
        self.assertEqual(remaining.label_aliases, ['alias_0', 'alias_1', 'primary'])
        for label in ['alias_0', 'alias_1', 'primary', 'existing']:
            self.assertIs(block.get_insn_by_label(label), remaining)
        self.assertEqual(str(remaining), 'alias_0:\nalias_1:\nprimary:\nexisting:\nremaining ')

    def test_removing_only_instruction_moves_all_labels_to_successor(self):
        block = IRBlock()
        successor = IRBlock()
        block.add_successor(successor)

        removed = UnknownNAC('removed', [], label_name='primary')
        removed.label_aliases = ['alias_0', 'alias_1']
        block.insert_insn(removed)
        first_successor_insn = UnknownNAC('successor', [], label_name='successor_label')
        successor.insert_insn(first_successor_insn)

        block.remove_insn(removed)

        self.assertEqual(first_successor_insn.label, 'successor_label')
        self.assertEqual(first_successor_insn.label_aliases, ['alias_0', 'alias_1', 'primary'])
        for label in ['alias_0', 'alias_1', 'primary', 'successor_label']:
            self.assertIs(successor.get_insn_by_label(label), first_successor_insn)

    def test_removing_non_first_instruction_unregisters_aliases(self):
        block = IRBlock()
        first = UnknownNAC('first', [], label_name='first_label')
        block.insert_insn(first)
        removed = UnknownNAC('removed', [], label_name='primary')
        removed.label_aliases = ['alias_0', 'alias_1']
        block.insert_insn(removed)
        third = UnknownNAC('third', [], label_name='third_label')
        block.insert_insn(third)

        block.remove_insn(removed)

        for label in ['primary', 'alias_0', 'alias_1']:
            self.assertIsNone(block.get_insn_by_label(label))
        self.assertIs(block.get_insn_by_label('first_label'), first)
        self.assertIs(block.get_insn_by_label('third_label'), third)


if __name__ == '__main__':
    unittest.main()
