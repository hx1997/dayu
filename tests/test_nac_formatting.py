import unittest

from decompile.ir.nac import AssignNAC, CallNAC, CondJumpNAC, ImportNAC, NAddressCodeType, ReturnNAC
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


if __name__ == '__main__':
    unittest.main()
