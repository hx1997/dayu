import contextlib
import io
import unittest

from decompile.config import DecompilerConfig, DecompileOutputLevel
from decompile.decompiler import Decompiler
from decompile.pa2rawir import Pandasm2RawIR
from decompile.passes.buildcfg import BuildCFG
from pandasm.reader import PandasmReader


def parse_method(body, directive=None):
    directive = directive or ('.catchall tb, te, hb' if 'te:' in body else '.catchall tb, hb, hb')
    text = '''# source binary: fixture.abc
# ====================
# LITERALS
# ====================
# RECORDS
.language ECMAScript
.record sample {
}
# ====================
# METHODS
.language ECMAScript
.function any sample.test(any a0, any a1, any a2, any a3) <static> {
''' + body + '\n' + directive + '\n}\n'
    return PandasmReader.from_buffer(text)


def raw_method(body, directive=None):
    module = Pandasm2RawIR.transform_module(parse_method(body, directive))
    return module.classes[0].methods[0]


TERMINAL = '''tb:
    lda a3
    callarg0 0x0
    return
hb:
    ldai 0x7
    return'''

JOIN = '''tb:
    lda a3
    callarg0 0x0
te:
    jmp done
hb:
    ldai 0x7
    sta v0
    jmp done
done:
    lda v0
    return'''

BRANCH = '''tb:
    lda a3
    callarg0 0x0
    return
hb:
    jeqz other
    ldai 0x7
    return
other:
    ldai 0x8
    return'''


class ThreeLabelCatchallTests(unittest.TestCase):
    def test_parser_keeps_missing_extent_unknown(self):
        pa = parse_method(TERMINAL)
        region = pa.classes['sample'].methods[0].try_catch_regions[0]
        self.assertIsNone(region.handler_end)
        self.assertEqual(region.handler_begin, 'hb')

    def test_terminal_handler_is_resolved(self):
        method = raw_method(TERMINAL)
        BuildCFG().run_on_method(method)
        bounds = method.resolved_try_regions[0]
        self.assertFalse(method.low_level_exception_fallback)
        self.assertEqual(bounds.handler_block_ids, {bounds.handler_entry_id})
        self.assertTrue(method.get_insn_by_label('hb').parent_block.exception_predecessors)

    def test_join_does_not_belong_to_handler(self):
        method = raw_method(JOIN)
        BuildCFG().run_on_method(method)
        bounds = method.resolved_try_regions[0]
        done = method.get_insn_by_label('done').parent_block
        self.assertFalse(method.low_level_exception_fallback)
        self.assertFalse(done.origin_block_ids & bounds.handler_block_ids)
        self.assertEqual(bounds.continuation_label, 'done')

    def test_unknown_extent_keeps_exception_edges_and_original_listing(self):
        method = raw_method(BRANCH)
        BuildCFG().run_on_method(method)
        bounds = method.resolved_try_regions[0]
        self.assertIsNone(bounds.handler_block_ids)
        self.assertTrue(method.low_level_exception_fallback)
        self.assertTrue(method.get_insn_by_label('hb').parent_block.exception_predecessors)
        self.assertIn('jeqz other', '\n'.join(method.exception_fallback_lines))
        self.assertIn('.catchall tb, hb, hb', method.exception_fallback_lines)

    def test_cycle_is_not_packaged_as_catch(self):
        method = raw_method(BRANCH.replace('jeqz other', 'jmp hb'))
        BuildCFG().run_on_method(method)
        self.assertTrue(method.low_level_exception_fallback)

    def test_shared_success_tail_is_not_swallowed(self):
        # The optimizer can put a success-only assignment before the shared tail.
        body = JOIN.replace('jmp done\nhb:', 'jmp success\nhb:').replace(
            'done:\n    lda v0', 'success:\n    mov v0, a3\ndone:\n    lda v0')
        method = raw_method(body)
        BuildCFG().run_on_method(method)
        self.assertTrue(method.low_level_exception_fallback)
        self.assertIsNone(method.resolved_try_regions[0].handler_block_ids)

    def test_protocol_handler_is_not_packaged_as_user_catch(self):
        method = raw_method(TERMINAL.replace('ldai 0x7', 'asyncfunctionreject v0'))
        BuildCFG().run_on_method(method)
        self.assertTrue(method.low_level_exception_fallback)

    def decompile(self, body):
        config = DecompilerConfig({
            'abc': object(),
            'pandasm': parse_method(body),
            'class': 'sample', 'method': 'test',
            'output_level': DecompileOutputLevel.PSEUDOCODE,
        })
        # These fixtures have no module requests and need no binary metadata.
        decompiler = Decompiler(config)
        method = raw_method(body)
        decompiler.decompile_method(method)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            decompiler.print_code(method)
        return output.getvalue()

    def test_terminal_handler_is_emitted(self):
        output = self.decompile(TERMINAL)
        self.assertIn('try {', output)
        self.assertIn('} catch {', output)
        self.assertIn('return 0x7', output)

    def test_join_continuation_is_emitted_after_catch(self):
        output = self.decompile(JOIN)
        self.assertIn('} catch {', output)
        self.assertGreater(output.rfind('return'), output.rfind('}'))
        self.assertNotIn('jump done', output)

    def test_fallback_prints_metadata_and_both_branch_arms(self):
        output = self.decompile(BRANCH)
        self.assertNotIn('Handler extent is unknown', output)
        self.assertIn('if (v0 == 0) jump other', output)
        self.assertIn('v0 = a0()', output)
        self.assertIn('return 0x7', output)
        self.assertIn('return 0x8', output)
        self.assertNotIn('} catch {', output)


if __name__ == '__main__':
    unittest.main()
