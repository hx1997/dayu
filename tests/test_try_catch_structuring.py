import unittest
from pathlib import Path

from ark.abcreader import AbcReader
from decompile.config import DecompilerConfig, DecompileGranularity, DecompileOutputLevel
from decompile.decompiler import Decompiler
from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod, ResolvedTryRegion
from pandasm.method import PandasmTryCatchRegion
from pandasm.reader import PandasmReader


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_ABC = REPO_ROOT / 'examples' / 'modules.12.abc'
MODULES_PANDASM = REPO_ROOT / 'examples' / 'modules.12.abc.txt'
IMAGE_ABC = REPO_ROOT / 'examples' / 'hwsample_image.abc'
IMAGE_PANDASM = REPO_ROOT / 'examples' / 'hwsample_image.abc.txt'


def decompile_method_output(abc_path, pandasm_path, class_name, method_name):
    abcfile = AbcReader.from_file(abc_path)
    pafile = PandasmReader.from_file(pandasm_path)
    config = DecompilerConfig({
        'abc': abcfile,
        'pandasm': pafile,
        'output_level': DecompileOutputLevel.PSEUDOCODE,
        'class': class_name,
        'method': method_name,
        'granularity': DecompileGranularity.METHOD,
    })
    method = Decompiler(config).decompile()
    return '\n'.join(str(insn) for block in method.blocks for insn in block.insns)


class TryCatchStructuringTests(unittest.TestCase):
    def test_exception_edges_are_separate_from_normal_edges(self):
        method = IRMethod('exception_edges')
        try_block = IRBlock(method)
        handler_block = IRBlock(method)
        continuation = IRBlock(method)
        try_block.origin_block_ids = {0}
        handler_block.origin_block_ids = {1}
        continuation.origin_block_ids = {2}
        try_block.add_successor(continuation)
        method.resolved_try_regions = [ResolvedTryRegion(
            region=PandasmTryCatchRegion('try_begin', 'try_end', 'handler_begin', 'handler_end'),
            try_block_ids={0},
            handler_block_ids={1},
        )]

        method.rebuild_exception_edges()

        self.assertEqual(try_block.successors, [continuation])
        self.assertEqual(try_block.exception_successors, [handler_block])
        self.assertEqual(handler_block.exception_predecessors, [try_block])
        self.assertEqual(handler_block.predecessors, [])

    def test_single_try_catch_is_emitted(self):
        output = decompile_method_output(
            MODULES_ABC,
            MODULES_PANDASM,
            'com.example.myapplication.entry.ets.entryability.EntryAbility',
            'func_main_0',
        )

        self.assertIn('try {', output)
        self.assertIn('} catch {', output)
        self.assertRegex(output, r'throw v\d+')

    def test_nested_try_regions_are_preserved(self):
        output = decompile_method_output(
            IMAGE_ABC,
            IMAGE_PANDASM,
            'ohos.samples.image.entry@photomodify.ets.components.pages.EditImage',
            'cropImage',
        )

        self.assertGreaterEqual(output.count('try {'), 2)
        self.assertGreaterEqual(output.count('} catch {'), 2)


if __name__ == '__main__':
    unittest.main()