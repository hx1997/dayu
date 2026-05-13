import logging
import typing
from collections import defaultdict

from decompile.class_pass import ClassPass
from decompile.ir.basicblock import IRBlock
from decompile.ir.insn_lifter import InsnLifter
from decompile.ir.irclass import IRClass
from decompile.ir.lexenv import LexEnv, LexVar
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCode, NAddressCodeType
from pandasm.insn import PandasmInsnArgument


class ResolveLexVar(ClassPass):
    """
    resolve lexical variables (lexvars) into actual names
    """
    def __init__(self):
        super().__init__()
        self.vis = set()
        self.current_lexenv = None
        self.lexenv_stack = []
        self.per_method_lexenvs = defaultdict(list)
        self.top_level_lexenv_on_block_exit = {}

    def run_on_class(self, clazz: IRClass):
        main_method: typing.Optional[IRMethod] = clazz.get_method_by_name('func_main_0')
        if not main_method:
            logging.getLogger(__name__).warning(
                '[%s] main method not found for class %s',
                self.__class__.__name__,
                clazz.name
            )
            return

        try:
            self.run_on_method(main_method)
        except:
            logging.getLogger(__name__).exception(
                '[%s] couldn\'t resolve LexVar for class %s',
                self.__class__.__name__,
                clazz.name
            )

    def run_on_method(self, method: IRMethod):
        self.do_run_on_method(method, None)

    def do_run_on_method(self, method: IRMethod, top_level_lexenv_on_entry: typing.Optional[LexEnv]):
        if self.current_lexenv is not None:
            self.lexenv_stack.append(self.current_lexenv)

        for block in method.blocks:
            if block not in self.vis:
                self.dfs(block, top_level_lexenv_on_entry)

        if len(self.lexenv_stack) > 0:
            self.current_lexenv = self.lexenv_stack.pop()

    def dfs(self, block: IRBlock, top_level_lexenv_on_entry: typing.Optional[LexEnv]):
        if block in self.vis:
            return
        self.vis.add(block)

        method_fullname = f'{block.parent_method.parent_class.name}.{block.parent_method.name}'

        for insn_idx, insn in enumerate(block.insns):
            insn: NAddressCode
            if insn.type == NAddressCodeType.UNKNOWN and insn.op == 'newlexenv':  # newlexenv (unlifted)
                self.handle_newlexenv(insn, method_fullname, top_level_lexenv_on_entry, False)
            elif insn.type == NAddressCodeType.VAR_DECL and isinstance(insn.var_names[0], PandasmInsnArgument) and insn.var_names[0].type == 'lexvar':  # newlexenv (lifted)
                self.handle_newlexenv(insn, method_fullname, top_level_lexenv_on_entry, True)
            elif insn.type == NAddressCodeType.UNKNOWN and insn.op == 'newlexenvwithname':  # newlexenvwithname (unlifted)
                self.handle_newlexenvwithname(insn, method_fullname, top_level_lexenv_on_entry, False)
            elif insn.type == NAddressCodeType.VAR_DECL and isinstance(insn.var_names[0], str):  # newlexenvwithname (lifted)
                self.handle_newlexenvwithname(insn, method_fullname, top_level_lexenv_on_entry, True)
            elif insn.type == NAddressCodeType.UNKNOWN and insn.op == 'poplexenv':  # poplexenv (unlifted)
                self.handle_poplexenv(insn, method_fullname)
            elif insn.type == NAddressCodeType.CALL and insn.func.value == '__poplexenv__':  # poplexenv (lifted)
                self.handle_poplexenv(insn, method_fullname)
            elif insn.type == NAddressCodeType.UNKNOWN and insn.op in ['definemethod', 'definefunc']:  # definemethod/definefunc (unlifted)
                self.handle_definemethod_definefunc(insn, method_fullname, top_level_lexenv_on_entry, False)
            elif insn.type == NAddressCodeType.ASSIGN and insn.extra_info and insn.extra_info[0] in ['definemethod', 'definefunc']:  # definemethod/definefunc (lifted)
                self.handle_definemethod_definefunc(insn, method_fullname, top_level_lexenv_on_entry, True)
            elif insn.type == NAddressCodeType.UNKNOWN and insn.op == 'defineclasswithbuffer':  # defineclasswithbuffer (unlifted)
                self.handle_defineclasswithbuffer(insn, method_fullname, top_level_lexenv_on_entry, False)
            elif insn.type == NAddressCodeType.CALL and insn.func.value == '__define_class__':  # defineclasswithbuffer (lifted)
                self.handle_defineclasswithbuffer(insn, method_fullname, top_level_lexenv_on_entry, True)
            else:
                # resolve lexvar uses (e.g. in stlexvar/ldlexvar)
                self.handle_lexvar_uses(insn)

            if insn_idx == len(block.insns) - 1:
                self.top_level_lexenv_on_block_exit[block] = self.current_lexenv

        for succ in block.successors:
            self.dfs(succ, self.top_level_lexenv_on_block_exit[block])

    def get_lexvar(self, lexenv_relative_level, lexvar_idx):
        # start from the top-level lexenv and go back `lexenv_relative_level` levels
        lexenv = self.current_lexenv
        for _ in range(abs(lexenv_relative_level)):
            lexenv = lexenv.parent_lexenv

        # return the `lexvar_idx`-th lexvar
        return lexenv.get_lexvar(lexvar_idx)

    def parse_defineclasswithbuffer(self, target_class, methods_arg):
        # { 7 [ string:"init", method:init, method_affiliate:0, string:"getInstance", method:getInstance, method_affiliate:0, i32:1, ]}

        methods = []
        # string:"init", method:init, method_affiliate:0, string:"getInstance", method:getInstance, method_affiliate:0, i32:1,
        methods_arg = methods_arg.split('[')[1].split(']')[0].strip()

        for methods_arg_split in methods_arg.split(','):
            if methods_arg_split.strip().startswith('method:'):
                method_name = methods_arg_split.split(':')[1]
                methods.append(target_class.get_method_by_name(method_name))

        return methods

    def handle_newlexenv(self, insn, method_fullname, top_level_lexenv_on_entry, lifted):
        block = insn.parent_block
        if self.per_method_lexenvs[method_fullname]:
            lexenv = LexEnv(block.parent_method, parent_lexenv=self.per_method_lexenvs[method_fullname][-1])
        else:
            lexenv = LexEnv(block.parent_method, parent_lexenv=top_level_lexenv_on_entry)

        num_lexenv = len(insn.args) if lifted else int(insn.args[1].value, 16)
        for i in range(num_lexenv):
            lexvar_name = f'lexvar_{lexenv.lexenv_level}_{i}'
            lexenv.add_lexvar(LexVar(lexenv.lexenv_level, lexvar_name))
            if lifted:
                insn.var_names[i] = PandasmInsnArgument('lexvar', lexvar_name)  # rename

        self.per_method_lexenvs[method_fullname].append(lexenv)
        self.current_lexenv = lexenv

    def handle_newlexenvwithname(self, insn, method_fullname, top_level_lexenv_on_entry, lifted):
        block = insn.parent_block
        if self.per_method_lexenvs[method_fullname]:
            lexenv = LexEnv(block.parent_method, parent_lexenv=self.per_method_lexenvs[method_fullname][-1])
        else:
            lexenv = LexEnv(block.parent_method, parent_lexenv=top_level_lexenv_on_entry)

        lexvar_names = insn.var_names if lifted else InsnLifter.parse_newlexenvwithname(insn.args[2].value)
        for name in lexvar_names:
            lexenv.add_lexvar(LexVar(lexenv.lexenv_level, name))

        self.per_method_lexenvs[method_fullname].append(lexenv)
        self.current_lexenv = lexenv

    def handle_poplexenv(self, insn, method_fullname):
        if self.current_lexenv:
            self.current_lexenv = self.current_lexenv.parent_lexenv
        if len(self.per_method_lexenvs[method_fullname]) > 0:
            self.per_method_lexenvs[method_fullname].pop()

        # FIXME: poplexenv should be erased but doing so here could lead to some jump labels being lost,
        #  e.g. when two adjacent NACs both have labels
        #  omitting erasure doesn't affect correctness, but will lower pseudocode readability
        # insn.erase_from_parent()

    def handle_definemethod_definefunc(self, insn, method_fullname, top_level_lexenv_on_entry, lifted):
        block = insn.parent_block
        target_method_fullname = str(insn.extra_info[1]) if lifted else str(insn.args[2])
        target_class_name = '.'.join(target_method_fullname.split(':')[0].split('.')[:-1])
        target_method_name = target_method_fullname.split(':')[0].split('.')[-1]
        target_class = block.parent_method.parent_class.parent_module.get_class_by_name(target_class_name)
        target_method = target_class.get_method_by_name(target_method_name)

        if self.per_method_lexenvs[method_fullname]:
            self.do_run_on_method(target_method, self.per_method_lexenvs[method_fullname][-1])
        else:
            self.do_run_on_method(target_method, top_level_lexenv_on_entry)

    def handle_defineclasswithbuffer(self, insn, method_fullname, top_level_lexenv_on_entry, lifted):
        block = insn.parent_block
        target_class_fullname = str(insn.call_args[0]) if lifted else str(insn.args[2])
        target_class_name = '.'.join(target_class_fullname.split(':')[0].split('.')[:-1])
        target_class = block.parent_method.parent_class.parent_module.get_class_by_name(target_class_name)

        method_string = str(insn.extra_info[0]) if lifted else str(insn.args[3])
        methods = self.parse_defineclasswithbuffer(target_class, method_string)
        for target_method in methods:
            if self.per_method_lexenvs[method_fullname]:
                self.do_run_on_method(target_method, self.per_method_lexenvs[method_fullname][-1])
            else:
                self.do_run_on_method(target_method, top_level_lexenv_on_entry)

    def handle_lexvar_uses(self, insn):
        def remap(arg):
            if isinstance(arg, PandasmInsnArgument) and arg.type == 'lexvar':
                lexenv_relative_level = int(arg.value.split('_')[1])
                lexvar_idx = int(arg.value.split('_')[2])
                lexvar = self.get_lexvar(lexenv_relative_level, lexvar_idx)
                return PandasmInsnArgument('lexvar', lexvar.lexvar_name)
            return arg
        insn.remap_args(remap)
