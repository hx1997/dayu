import sys

from decompile.config import DecompilerConfig, DecompileGranularity, DecompileOutputLevel
from decompile.ir.irclass import IRClass
from decompile.ir.method import IRMethod
from decompile.ir.module import IRModule
from decompile.pa2rawir import Pandasm2RawIR
from decompile.passes.buildcfg import BuildCFG
from decompile.passes.control_flow_structuring import ControlFlowStructuring
from decompile.passes.copy_propagation import CopyPropagation
from decompile.passes.dead_code import DeadCodeElimination
from decompile.passes.defuse import DefUseAnalysis
from decompile.passes.print_pcode import PrintPcode
from decompile.passes.live_variable import LiveVariableAnalysis
from decompile.passes.peephole_opt import PeepholeOptimization
from decompile.passes.rawir2llir import RawIR2LLIR
from decompile.passes.var_alloc import VariableAllocation
from decompile.passes.viewcfg import ViewCFG


class Decompiler:
    def __init__(self, config: DecompilerConfig):
        self.config = config
        self.check_config()
        self.ir_module: IRModule | None = None
        self.decompiled_ir_level = None

    def check_config(self):
        if self.config.abc_file is None or self.config.pandasm_file is None:
            raise Exception(f'[{self.__class__.__name__}] error: input abc file or pandasm file not specified')

        if not isinstance(self.config.granularity, DecompileGranularity):
            raise Exception(f'[{self.__class__.__name__}] error: invalid decompilation granularity')

        if self.config.granularity is DecompileGranularity.CLASS and self.config.target_class == '':
            raise Exception(f'[{self.__class__.__name__}] error: class to be decompiled not specified')

        if self.config.granularity is DecompileGranularity.METHOD and self.config.target_class == '':
            raise Exception(f'[{self.__class__.__name__}] error: declaring class of method to be decompiled not specified')

        if self.config.granularity is DecompileGranularity.METHOD and self.config.target_method == '':
            raise Exception(f'[{self.__class__.__name__}] error: method to be decompiled not specified')

        if not isinstance(self.config.output_level, DecompileOutputLevel):
            raise Exception(f'[{self.__class__.__name__}] error: invalid decompiler output level')

        if self.config.max_no_mlir_passes_iterations < -1:
            raise Exception(f'[{self.__class__.__name__}] error: invalid max number of iterations for MLIR passes')

        for level in self.config.copy_propagation_enabled_levels:
            if level not in [DecompileOutputLevel.MEDIUM_LEVEL_IR, DecompileOutputLevel.HIGH_LEVEL_IR]:
                raise Exception(f'[{self.__class__.__name__}] error: copy propagation only available in MLIR or HLIR')

        for level in self.config.dead_code_elimination_enabled_levels:
            if level not in [DecompileOutputLevel.MEDIUM_LEVEL_IR, DecompileOutputLevel.HIGH_LEVEL_IR]:
                raise Exception(f'[{self.__class__.__name__}] error: dead code elimination only available in MLIR or HLIR')

        for level in self.config.peephole_optimization_enabled_levels:
            if level not in [DecompileOutputLevel.MEDIUM_LEVEL_IR, DecompileOutputLevel.HIGH_LEVEL_IR]:
                raise Exception(f'[{self.__class__.__name__}] error: peephole optimization only available in MLIR or HLIR')

    def decompile(self):
        self.ir_module = self.pandasm_to_rawir()
        self.decompiled_ir_level = DecompileOutputLevel.RAW_IR

        if self.config.granularity is DecompileGranularity.MODULE:
            return self.decompile_module()
        elif self.config.granularity is DecompileGranularity.CLASS:
            for clz in self.ir_module.classes:
                if clz.name == self.config.target_class:
                    return self.decompile_class(clz)
        elif self.config.granularity is DecompileGranularity.METHOD:
            for clz in self.ir_module.classes:
                if clz.name != self.config.target_class:
                    continue
                for method in clz.methods:
                    if method.name == self.config.target_method:
                        return self.decompile_method(method)
        else:
            raise Exception(f'[{self.__class__.__name__}] error: invalid decompilation granularity')

    def decompile_module(self):
        for clz in self.ir_module.classes:
            self.decompile_class(clz)
        return self.ir_module

    def decompile_class(self, clz: IRClass):
        for method in clz.methods:
            self.decompile_method(method)
        return clz

    def decompile_method(self, method: IRMethod):
        if self.config.output_level is DecompileOutputLevel.RAW_IR:
            return method

        self.rawir_to_llir(method)
        self.decompiled_ir_level = DecompileOutputLevel.LOW_LEVEL_IR
        if self.config.output_level is DecompileOutputLevel.LOW_LEVEL_IR:
            if self.config.view_cfg:
                self.write_cfg_to_file(method, f'cfg/cfg_{method.name}', True)
                print(f'CFG saved to cfg/cfg_{method.name}.png', end='\n')
            return method

        self.llir_to_mlir(method)
        self.decompiled_ir_level = DecompileOutputLevel.MEDIUM_LEVEL_IR
        if self.config.output_level is DecompileOutputLevel.MEDIUM_LEVEL_IR:
            if self.config.view_cfg:
                self.write_cfg_to_file(method, f'cfg/cfg_{method.name}', True)
                print(f'CFG saved to cfg/cfg_{method.name}.png', end='\n')
            return method

        self.mlir_to_hlir(method)
        self.decompiled_ir_level = DecompileOutputLevel.HIGH_LEVEL_IR
        if self.config.output_level is DecompileOutputLevel.HIGH_LEVEL_IR:
            if self.config.view_cfg:
                self.write_cfg_to_file(method, f'cfg/cfg_{method.name}', True)
                print(f'CFG saved to cfg/cfg_{method.name}.png', end='\n')
            return method

        self.hlir_to_pseudocode(method)
        self.decompiled_ir_level = DecompileOutputLevel.PSEUDOCODE
        if self.config.output_level is DecompileOutputLevel.PSEUDOCODE:
            if self.config.view_cfg:
                self.write_cfg_to_file(method, f'cfg/cfg_{method.name}', True)
                print(f'CFG saved to cfg/cfg_{method.name}.png', end='\n')
            return method

        return method

    def pandasm_to_rawir(self):
        return Pandasm2RawIR.transform_module(self.config.pandasm_file, self.config.abc_file)

    def rawir_to_llir(self, method: IRMethod):
        BuildCFG().run_on_method(method)
        # convert to low-level IR
        RawIR2LLIR().run_on_method(method)

    def llir_to_mlir(self, method: IRMethod):
        # convert to medium-level IR
        method_insn_cnt_old = method.count_insns()
        is_first = True
        method_changed = False
        run_times = 0
        while is_first or method_changed:
            if self.config.max_no_mlir_passes_iterations == 0:
                break
            is_first = False
            # in_r, out_r = ReachingDefinitions().run_on_method(method)
            if DecompileOutputLevel.MEDIUM_LEVEL_IR in self.config.copy_propagation_enabled_levels:
                CopyPropagation(constrained=True).run_on_method(method)

            DefUseAnalysis().run_on_method(method)
            in_l, out_l = LiveVariableAnalysis().run_on_method(method)
            if DecompileOutputLevel.MEDIUM_LEVEL_IR in self.config.dead_code_elimination_enabled_levels:
                DeadCodeElimination(out_l).run_on_method(method)

            # update liveness
            DefUseAnalysis().run_on_method(method)
            in_l, out_l = LiveVariableAnalysis().run_on_method(method)
            if DecompileOutputLevel.MEDIUM_LEVEL_IR in self.config.peephole_optimization_enabled_levels:
                PeepholeOptimization(out_l, constrained=True).run_on_method(method)

            # run any user-specified extra passes
            for extra_pass in self.config.extra_mlir_passes:
                pass_, args = extra_pass
                pass_(*args).run_on_method(method)

            # if method hasn't changed, we've reached the fixed point
            method_changed = (method_insn_cnt_old != method.count_insns())
            if method_changed:
                method_insn_cnt_old = method.count_insns()

            run_times += 1
            if run_times >= self.config.max_no_mlir_passes_iterations != -1:
                break

    def mlir_to_hlir(self, method: IRMethod):
        # convert to high-level IR
        # in_r, out_r = ReachingDefinitions().run_on_method(method)
        if DecompileOutputLevel.HIGH_LEVEL_IR in self.config.copy_propagation_enabled_levels:
            CopyPropagation(constrained=False).run_on_method(method)

        DefUseAnalysis().run_on_method(method)
        in_l, out_l = LiveVariableAnalysis().run_on_method(method)
        if DecompileOutputLevel.HIGH_LEVEL_IR in self.config.dead_code_elimination_enabled_levels:
            DeadCodeElimination(out_l).run_on_method(method)

        # update liveness
        DefUseAnalysis().run_on_method(method)
        in_l, out_l = LiveVariableAnalysis().run_on_method(method)
        if DecompileOutputLevel.HIGH_LEVEL_IR in self.config.peephole_optimization_enabled_levels:
            PeepholeOptimization(out_l, constrained=False).run_on_method(method)

    def hlir_to_pseudocode(self, method: IRMethod):
        # convert to pseudocode
        if self.config.rename_variables:
            VariableAllocation().run_on_method(method)
        ControlFlowStructuring(self.config.recover_control_flow_structures).run_on_method(method)

    @staticmethod
    def write_cfg_to_file(method: IRMethod, output_path, view=False):
        ViewCFG(output_path, view).run_on_method(method)

    def print_ir(self, method: IRMethod):
        if self.decompiled_ir_level is DecompileOutputLevel.PSEUDOCODE:
            print('error: only IR can be printed', file=sys.stderr, flush=True)
        else:
            for block in method.blocks:
                for insn in block.insns:
                    print(insn)

    def print_pseudocode(self, method: IRMethod):
        if self.decompiled_ir_level is not DecompileOutputLevel.PSEUDOCODE:
            print('error: only pseudocode can be printed', file=sys.stderr, flush=True)
        else:
            PrintPcode().run_on_method(method)

    def print_code(self, method: IRMethod):
        if self.decompiled_ir_level is DecompileOutputLevel.PSEUDOCODE:
            self.print_pseudocode(method)
        else:
            self.print_ir(method)
