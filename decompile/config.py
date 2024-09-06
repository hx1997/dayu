import typing
from enum import IntEnum, auto


class DecompilerConfig:
    def __init__(self, config=None):
        self.set_default_config()

        if config is not None:
            self.set_config(config)

    def set_default_config(self):
        self.abc_file = None
        self.pandasm_file = None
        self.granularity: DecompileGranularity = DecompileGranularity.METHOD

        # name of method/class (depending on the granularity) to decompile; if granularity is MODULE, these are ignored
        self.target_class = ''
        self.target_method = ''

        self.output_level: DecompileOutputLevel = DecompileOutputLevel.PSEUDOCODE

        # the maximum number of times of running MLIR passes; -1 means run until fixed point,
        # 0 means skip these passes altogether
        self.max_no_mlir_passes_iterations = -1

        # on which IR levels should builtin optimization passes be run
        self.copy_propagation_enabled_levels: typing.Set[DecompileOutputLevel] = {DecompileOutputLevel.HIGH_LEVEL_IR}
        self.dead_code_elimination_enabled_levels: typing.Set[DecompileOutputLevel] = {
            DecompileOutputLevel.MEDIUM_LEVEL_IR, DecompileOutputLevel.HIGH_LEVEL_IR}
        self.peephole_optimization_enabled_levels: typing.Set[DecompileOutputLevel] = {
            DecompileOutputLevel.MEDIUM_LEVEL_IR, DecompileOutputLevel.HIGH_LEVEL_IR}

        # should we rename the variables, or just keep them as they are in Panda Assembly
        self.rename_variables = True

        # should we try to recover high-level control flow structures
        self.recover_control_flow_structures = True

        # should we prettify method calls (i.e. remove the first three convention-defined arguments FunctionObject,
        # NewTarget, and this) and rename method arguments (i.e. a3 -> a0, a4 -> a1, etc)
        self.prettify_method_calls = True

        # passes in this list will be run after the builtin MLIR passes
        # each element should be a tuple (subclass of MethodPass, list of arguments to the constructor)
        self.extra_mlir_passes: typing.List[typing.Tuple[typing.Callable, typing.List]] = []

        self.view_cfg = False

    def set_config(self, config: dict):
        self.abc_file = config.get('abc', self.abc_file)
        self.pandasm_file = config.get('pandasm', self.pandasm_file)
        self.granularity = config.get('granularity', self.granularity)
        self.target_class = config.get('class', self.target_class)
        self.target_method = config.get('method', self.target_method)
        self.output_level = config.get('output_level', self.output_level)
        self.max_no_mlir_passes_iterations = config.get('max_no_mlir_passes_iterations',
                                                        self.max_no_mlir_passes_iterations)
        self.copy_propagation_enabled_levels = config.get('copy_propagation_enabled_levels',
                                                          self.copy_propagation_enabled_levels)
        self.dead_code_elimination_enabled_levels = config.get('dead_code_elimination_enabled_levels',
                                                               self.dead_code_elimination_enabled_levels)
        self.peephole_optimization_enabled_levels = config.get('peephole_optimization_enabled_levels',
                                                               self.peephole_optimization_enabled_levels)
        self.rename_variables = config.get('rename_variables', self.rename_variables)
        self.recover_control_flow_structures = config.get('recover_control_flow_structures',
                                                          self.recover_control_flow_structures)
        self.prettify_method_calls = config.get('prettify_method_calls', self.prettify_method_calls)
        self.extra_mlir_passes = config.get('extra_mlir_passes', self.extra_mlir_passes)
        self.view_cfg = config.get('view_cfg', self.view_cfg)


class DecompileOutputLevel(IntEnum):
    RAW_IR = auto()
    LOW_LEVEL_IR = auto()
    MEDIUM_LEVEL_IR = auto()
    HIGH_LEVEL_IR = auto()
    PSEUDOCODE = auto()


class DecompileGranularity(IntEnum):
    METHOD = auto()
    CLASS = auto()
    MODULE = auto()
