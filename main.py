import argparse
import sys

from ark.abcreader import AbcReader
from decompile.config import DecompilerConfig, DecompileGranularity, DecompileOutputLevel
from decompile.decompiler import Decompiler
from pandasm.reader import PandasmReader


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-pc', '--print-classes', action='store_true', help='print names of all classes')
    parser.add_argument('-pmc', '--print-methods-in-class', metavar='CLASS', type=str, help='print names of all methods (including its class name) in the specified CLASS')
    parser.add_argument('-dmo', '--decompile-module', action='store_true', help='decompile the whole file')
    parser.add_argument('-dc', '--decompile-class', type=str, help='decompile all methods in the specified class')
    parser.add_argument('-dme', '--decompile-method', type=str, help='decompile the specified method; must be specified in the format "<class name>.<method name>"')
    parser.add_argument('-cfg', '--view-cfg', action='store_true', help='display the Control Flow Graph (CFG) of the specified method (graphviz required); must specify method with -dme')
    parser.add_argument('-abc', type=str, help='specify the input abc file')
    parser.add_argument('-pa', type=str, help='specify the input text-form Panda Assembly file')
    parser.add_argument('-O', '--output-level', type=str, help='output decompiled code at the specified level (possible values: llir, mlir, hlir, pcode, default: pcode)')
    args = parser.parse_args()
    return args

def print_names(args, abcfile, pafile):
    if args.print_classes:
        if args.abc:
            print(f'Classes from file {args.abc}:')
            for clz in abcfile.iter_classes():
                print(clz.name)
            print('')

        if args.pa:
            print(f'Classes from file {args.pa}:')
            for clz in pafile.iter_classes():
                print(clz.name)
            print('')

    if args.print_methods_in_class:
        if args.abc:
            print('error: parsing methods in abc files not implemented yet', file=sys.stderr)
            # print(f'Methods in class {args.print_methods_in_class} from file {args.abc}:')
            # clz = abcfile.get_class_by_name(args.print_methods_in_class)
            # for method in clz.methods:
            #     print(method.name)
            # print('')

        if args.pa:
            print(f'Methods in class {args.print_methods_in_class} from file {args.pa}:')
            clz = pafile.get_class_by_name(args.print_methods_in_class)
            for method in clz.methods:
                print(f'{clz.name}.{method.name}')
            print('')

def decompile(args, abcfile, pafile):
    if not abcfile:
        print('error: decompilation requires abc file, please specify', file=sys.stderr)
        exit(-1)

    if not pafile:
        print('error: decompilation requires Panda Assembly, please specify', file=sys.stderr)
        exit(-1)

    num_decompile_args = 0
    if args.decompile_module:
        num_decompile_args += 1
    if args.decompile_class:
        num_decompile_args += 1
    if args.decompile_method:
        num_decompile_args += 1
    if num_decompile_args > 1:
        print('error: please specify only one of -dmo, -dc, or -dme', file=sys.stderr)
        exit(-1)

    output_level_str_to_obj = {
        'llir': DecompileOutputLevel.LOW_LEVEL_IR,
        'mlir': DecompileOutputLevel.MEDIUM_LEVEL_IR,
        'hlir': DecompileOutputLevel.HIGH_LEVEL_IR,
        'pcode': DecompileOutputLevel.PSEUDOCODE
    }
    config = DecompilerConfig({
        'abc': abcfile,
        'pandasm': pafile,
        'output_level': output_level_str_to_obj[args.output_level] if args.output_level else DecompileOutputLevel.PSEUDOCODE,
        'view_cfg': args.view_cfg
    })
    if args.decompile_method:
        config.set_config({
            'class': '.'.join(args.decompile_method.split('.')[:-1]),
            'method': args.decompile_method.split('.')[-1],
            'granularity': DecompileGranularity.METHOD
        })
        decompiler = Decompiler(config)
        method = decompiler.decompile()
        print(f'Decompiled method {args.decompile_method} in class {args.decompile_class}:', flush=True)
        decompiler.print_code(method)
        print('', flush=True)
    elif args.decompile_class:
        config.set_config({
            'class': args.decompile_class,
            'granularity': DecompileGranularity.CLASS
        })
        decompiler = Decompiler(config)
        clz = decompiler.decompile()
        for method in clz.methods:
            print(f'Decompiled method {method.name} in class {args.decompile_class}:', flush=True)
            decompiler.print_code(method)
            print('', flush=True)
    elif args.decompile_module:
        config.set_config({
            'granularity': DecompileGranularity.MODULE
        })
        decompiler = Decompiler(config)
        module = decompiler.decompile()
        for clz in module.classes:
            for method in clz.methods:
                print(f'Decompiled method {method.name} in class {clz.name}:', flush=True)
                decompiler.print_code(method)
                print('', flush=True)


if __name__ == '__main__':
    args = parse_args()
    if not args.abc and not args.pa:
        print('error: no input file', file=sys.stderr)
        exit(-1)

    abcfile, pafile = None, None
    if args.abc:
        abcfile = AbcReader.from_file(args.abc)

    if args.pa:
        pafile = PandasmReader.from_file(args.pa)

    print_names(args, abcfile, pafile)
    decompile(args, abcfile, pafile)
