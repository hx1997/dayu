import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ark.abcreader import AbcReader
from decompile.config import DecompilerConfig, DecompileGranularity, DecompileOutputLevel
from decompile.decompiler import Decompiler
from pandasm.reader import PandasmReader


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ABC = REPO_ROOT / 'examples' / 'modules.12.abc'
EXAMPLE_PANDASM = REPO_ROOT / 'examples' / 'modules.12.abc.txt'
EXAMPLE_CLASS = 'com.example.myapplication.entry.ets.pages.Index'
EXAMPLE_METHOD = 'foo'
IMAGE_EXAMPLE_ABC = REPO_ROOT / 'examples' / 'hwsample_image.abc'
IMAGE_EXAMPLE_PANDASM = REPO_ROOT / 'examples' / 'hwsample_image.abc.txt'
IMAGE_EXAMPLE_CLASS = 'ohos.samples.image.entry@photomodify.ets.components.util.ImageUtil'
IMAGE_EXAMPLE_METHOD = 'getContainSize'
EXAMPLE_PAIRS = [
    (EXAMPLE_ABC, EXAMPLE_PANDASM),
    (IMAGE_EXAMPLE_ABC, IMAGE_EXAMPLE_PANDASM),
]


class IntegrationTests(unittest.TestCase):
    def decompile_method_output(self, abc_path, pandasm_path, class_name, method_name):
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

        decompiler = Decompiler(config)
        method = decompiler.decompile()
        return '\n'.join(str(insn) for block in method.blocks for insn in block.insns)

    def test_all_bundled_example_pairs_load(self):
        for abc_path, pandasm_path in EXAMPLE_PAIRS:
            with self.subTest(abc=abc_path.name, pandasm=pandasm_path.name):
                abcfile = AbcReader.from_file(abc_path)
                pafile = PandasmReader.from_file(pandasm_path)

                self.assertGreater(len(abcfile.classes), 0)
                self.assertGreater(len(pafile.classes), 0)

    def test_decompile_example_method_matches_golden_snippets(self):
        output = self.decompile_method_output(EXAMPLE_ABC, EXAMPLE_PANDASM, EXAMPLE_CLASS, EXAMPLE_METHOD)

        self.assertIn('while (v0 < 0x5) {', output)
        self.assertIn("import { default } as hilog from '@ohos:hilog';", output)
        self.assertIn("if (v1 == true) throw 'Value of \"hilog\" is undefined'", output)
        self.assertIn('return v2', output)

    def test_decompile_hwsample_image_method_matches_golden_snippets(self):
        output = self.decompile_method_output(
            IMAGE_EXAMPLE_ABC,
            IMAGE_EXAMPLE_PANDASM,
            IMAGE_EXAMPLE_CLASS,
            IMAGE_EXAMPLE_METHOD,
        )

        self.assertIn('v2.width = a0', output)
        self.assertIn('v2.height = ((a0 / a2) * a3)', output)
        self.assertIn('v2.height = a1', output)
        self.assertIn('v2.width = ((a1 / a3) * a2)', output)
        self.assertIn('v2.scale = (v8["width"] / a2)', output)
        self.assertIn('return v1', output)

    def test_cli_output_file_writes_decompiled_code(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'decompiled.txt'
            result = subprocess.run(
                [
                    sys.executable,
                    'main.py',
                    '-abc', str(EXAMPLE_ABC),
                    '-pa', str(EXAMPLE_PANDASM),
                    '-dme', f'{EXAMPLE_CLASS}.{EXAMPLE_METHOD}',
                    '-o', str(output_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertTrue(output_path.exists())

            output_text = output_path.read_text(encoding='utf-8')
            self.assertIn('Decompiled method foo in class', output_text)
            self.assertIn('while (v0 < 0x5) {', output_text)

    def test_missing_method_raises_clear_exception(self):
        abcfile = AbcReader.from_file(EXAMPLE_ABC)
        pafile = PandasmReader.from_file(EXAMPLE_PANDASM)
        config = DecompilerConfig({
            'abc': abcfile,
            'pandasm': pafile,
            'output_level': DecompileOutputLevel.PSEUDOCODE,
            'class': EXAMPLE_CLASS,
            'method': 'does_not_exist',
            'granularity': DecompileGranularity.METHOD,
        })

        decompiler = Decompiler(config)
        with self.assertRaisesRegex(Exception, 'method "does_not_exist" not found'):
            decompiler.decompile()


if __name__ == '__main__':
    unittest.main()
