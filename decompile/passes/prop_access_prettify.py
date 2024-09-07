import re

from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.method_pass import MethodPass
from pandasm.insn import PandasmInsnArgument


class PropAccessPrettify(MethodPass):
    def run_on_method(self, method: IRMethod):
        for block in method.blocks:
            self.run_on_block(block)

    def run_on_block(self, block: IRBlock):
        for insn in block.insns:
            for arg in insn.args:
                if not isinstance(arg, PandasmInsnArgument):
                    continue
                self.prop_access_bracket_to_dot(arg)

    def is_valid_js_property_name(self, prop_name):
        # note: this method is not 100% accurate
        reserved_words = [
            'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger', 'default', 'delete', 'do', 'else',
            'export', 'extends', 'false', 'finally', 'for', 'function', 'if', 'import', 'in', 'instanceof', 'new',
            'null', 'return', 'super', 'switch', 'this', 'throw', 'true', 'try', 'typeof', 'var', 'void', 'while',
            'with'
        ]
        prop_name_regex = r'^[_$a-zA-Z\xA0-\uFFFF][_$a-zA-Z0-9\xA0-\uFFFF]*$'
        if prop_name in reserved_words:
            return False
        if re.match(prop_name_regex, prop_name):
            return True
        return False

    def prop_access_bracket_to_dot(self, arg: PandasmInsnArgument):
        # turn "this['xxx']" into "this.xxx"
        if arg.ref_obj and isinstance(arg.ref_obj, PandasmInsnArgument):
            self.prop_access_bracket_to_dot(arg.ref_obj)
        if arg.type == 'field':
            if not isinstance(arg.value, str):
                return
            prop_name = arg.value.strip('"')
            # only valid identifier names can be used in a dot notation call
            if not self.is_valid_js_property_name(prop_name):
                return

            arg.type = 'func'  # not necessarily a function actually... just for convenience
            arg.value = f'{str(arg.ref_obj)}.{prop_name}'
