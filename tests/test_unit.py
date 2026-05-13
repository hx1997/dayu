import unittest
from pathlib import Path

from dataflow_example import create_example_method
from decompile.passes.defuse import DefUseAnalysis
from decompile.passes.live_variable import LiveVariableAnalysis
from decompile.passes.reaching_def import ReachingDefinitions
from pandasm.reader import PandasmReader


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_PANDASM = REPO_ROOT / 'examples' / 'modules.12.abc.txt'
MODULES_CLASS = 'com.example.myapplication.entry.ets.pages.Index'


class PandasmReaderUnitTests(unittest.TestCase):
    def test_from_file_parses_expected_class_and_method(self):
        pandasm = PandasmReader.from_file(MODULES_PANDASM)

        self.assertEqual(pandasm.source_binary, 'modules.12.abc')
        self.assertEqual(pandasm.language, 'ECMAScript')

        page_class = pandasm.get_class_by_name(MODULES_CLASS)
        self.assertIsNotNone(page_class)
        self.assertIn('foo', [method.name for method in page_class.methods])

    def test_from_buffer_matches_from_file_class_names(self):
        file_parsed = PandasmReader.from_file(MODULES_PANDASM)
        buffer_parsed = PandasmReader.from_buffer(MODULES_PANDASM.read_text(encoding='utf8', errors='ignore'))

        self.assertEqual(sorted(file_parsed.classes.keys()), sorted(buffer_parsed.classes.keys()))


class DataflowUnitTests(unittest.TestCase):
    def test_defuse_analysis_populates_expected_block_sets(self):
        method = create_example_method()
        DefUseAnalysis().run_on_method(method)

        actual = [
            (
                {str(value) for value in block.defs},
                {str(value) for value in block.uses},
            )
            for block in method.blocks
        ]
        expected = [
            ({'v0', 'v1'}, {'5'}),
            ({'v2'}, {'10', '15', 'label_block3', 'v1'}),
            ({'v1'}, {'20', 'label_block3'}),
            (set(), {'v1'}),
        ]

        self.assertEqual(actual, expected)

    def test_reaching_definitions_reports_expected_in_out_sets(self):
        method = create_example_method()
        in_block, out_block = ReachingDefinitions().run_on_method(method)

        actual_in = [{str(insn) for insn in in_block.get(block, set())} for block in method.blocks]
        actual_out = [{str(insn) for insn in out_block.get(block, set())} for block in method.blocks]

        expected_in = [
            set(),
            {'v0 = = 5', 'v1 = = v0'},
            {'v0 = = 5', 'v1 = = v0', 'v2 = v1 + 10'},
            {'v0 = = 5', 'v1 = = 20', 'v1 = = v0', 'v2 = v1 + 10'},
        ]
        expected_out = [
            {'v0 = = 5', 'v1 = = v0'},
            {'v0 = = 5', 'v1 = = v0', 'v2 = v1 + 10'},
            {'v0 = = 5', 'v1 = = 20', 'v2 = v1 + 10'},
            {'v0 = = 5', 'v1 = = 20', 'v1 = = v0', 'v2 = v1 + 10'},
        ]

        self.assertEqual(actual_in, expected_in)
        self.assertEqual(actual_out, expected_out)

    def test_live_variable_analysis_reports_expected_in_out_sets(self):
        method = create_example_method()
        DefUseAnalysis().run_on_method(method)
        in_block, out_block = LiveVariableAnalysis().run_on_method(method)

        actual_in = [{str(value) for value in in_block.get(block, set())} for block in method.blocks]
        actual_out = [{str(value) for value in out_block.get(block, set())} for block in method.blocks]

        expected_in = [
            {'10', '15', '20', '5', 'label_block3'},
            {'10', '15', '20', 'label_block3', 'v1'},
            {'20', 'label_block3'},
            {'v1'},
        ]
        expected_out = [
            {'10', '15', '20', 'label_block3', 'v1'},
            {'20', 'label_block3', 'v1'},
            {'v1'},
            set(),
        ]

        self.assertEqual(actual_in, expected_in)
        self.assertEqual(actual_out, expected_out)


if __name__ == '__main__':
    unittest.main()