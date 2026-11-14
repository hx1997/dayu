import unittest

from decompile.ir.basicblock import IRBlock
from decompile.ir.expr import ExprArg
from decompile.ir.method import IRMethod
from decompile.ir.nac import AssignNAC, ReturnNAC
from decompile.passes.prop_access_prettify import PropAccessPrettify
from decompile.passes.var_alloc import VariableAllocation
from pandasm.insn import PandasmInsnArgument as Arg


class NestedPropertyRenderingTests(unittest.TestCase):
    def test_property_base_inside_expression_is_renamed_and_prettified(self):
        method = IRMethod('nested_property')
        block = IRBlock(method)
        width = Arg('field', 'width', Arg('acc'))
        expression = ExprArg([width, Arg('str', '"*"')], 'arith', '+')
        assignment = AssignNAC('+', Arg('acc'), expression, Arg('reg', 'v7'))
        block.insert_insn(assignment)
        block.insert_insn(ReturnNAC(Arg('acc')))

        VariableAllocation(True).run_on_method(method)
        self.assertEqual(width.ref_obj.type, 'var')
        self.assertEqual(width.ref_obj.value, assignment.dst.value)
        PropAccessPrettify().run_on_method(method)

        self.assertEqual(str(assignment), 'v0 = (v0.width + "*") + v1')
        self.assertNotIn('acc', str(assignment))


if __name__ == '__main__':
    unittest.main()
