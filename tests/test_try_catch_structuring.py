import unittest
from pathlib import Path

from ark.abcreader import AbcReader
from decompile.config import DecompilerConfig, DecompileGranularity, DecompileOutputLevel
from decompile.decompiler import Decompiler
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