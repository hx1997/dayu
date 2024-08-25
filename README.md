[简体中文](README_zh_simp.md) | **English**

# dayu
dayu (pronounced /ta˥˨ y˨˦/, loosely daa-jyu /dɑːjuː/) is a parser and (very rudimentary) decompiler for the .abc files (Ark Bytecode files) used on Open/HarmonyOS.

*Dayu*, or [Yu the Great](https://en.wikipedia.org/wiki/Yu_the_Great), was an ancient Chinese king credited with successfully coping with the Great Flood and thus saving people from suffering. On a similar note, Noah's Ark helped lives survive the Deluge. In a broad sense, dayu represented/represents Ark in another form. 

**Disclaimer**: dayu is a toy project developed in my free time. My availability and expertise are limited, so decompilation correctness and future maintenance are NOT guaranteed. Use at your own risk.

## Usage
### As a standalone command-line tool
```
usage: main.py [-h] [-pc] [-pmc CLASS] [-dmo] [-dc DECOMPILE_CLASS] [-dme DECOMPILE_METHOD] [-cfg] [-abc ABC] [-pa PA]
               [-O OUTPUT_LEVEL]

options:
  -h, --help            show this help message and exit
  -pc, --print-classes  print names of all classes
  -pmc CLASS, --print-methods-in-class CLASS
                        print names of all methods (including its class name) in the specified CLASS
  -dmo, --decompile-module
                        decompile the whole file
  -dc DECOMPILE_CLASS, --decompile-class DECOMPILE_CLASS
                        decompile all methods in the specified class
  -dme DECOMPILE_METHOD, --decompile-method DECOMPILE_METHOD
                        decompile the specified method; must be specified in the format "<class name>.<method name>"
  -cfg, --view-cfg      display the Control Flow Graph (CFG) of the specified method (graphviz required); must specify
                        method with -dme
  -abc ABC              specify the input abc file
  -pa PA                specify the input text-form Panda Assembly file
  -O OUTPUT_LEVEL, --output-level OUTPUT_LEVEL
                        output decompiled code at the specified level (possible values: llir, mlir, hlir, pcode,
                        default: pcode)
```

### In Python code
Example:

```python
from ark.abcreader import AbcReader
from decompile.config import DecompilerConfig, DecompileGranularity, DecompileOutputLevel
from decompile.decompiler import Decompiler
from pandasm.reader import PandasmReader

# specify input files, Panda Assembly file (obtained by using ark_disasm tool from the SDK) is required for decompilation
abcfile = AbcReader.from_file('<path to abc file>')
pafile = PandasmReader.from_file('<path to Panda Assembly file>')

# configure the decompiler
config = DecompilerConfig({
        'abc': abcfile,
        'pandasm': pafile,
        'output_level': DecompileOutputLevel.PSEUDOCODE
    })
config.set_config({
    'class': '<name of class containing the method to decompile>',
    'method': '<name of method to decompile>',
    'granularity': DecompileGranularity.METHOD
})

# ready, steady, go!
decompiler = Decompiler(config)
method = decompiler.decompile()

# print the decompiled code
decompiler.print_code(method)

# view the CFG
decompiler.write_cfg_to_file(method, f'cfg/cfg_{method.name}', True)
```

## Caveats
As much as dayu tries to output code that conforms to the syntax of ArkTS, this isn't always possible or easy to achieve (for me). Some points to note:  

First, since dayu is still limited in its control flow structure recovery, the final pseudocode may well be littered with `goto`s (in the form of `jump` statements). ArkTS (as well as TypeScript) doesn't support `goto`, so the user will have to sort most of the control flow out for themselves.

Second, in the final pseudocode, there may be some "pseudo-functions". They stand for operations that can't be easily translated. For example, retrieving [lexical environment](https://gitee.com/openharmony/docs/blob/master/en/application-dev/quick-start/arkts-bytecode-fundamentals.md#lexical-environment-and-lexical-variable) is represented as `__get_lexenv__`.

Some pseudo-functions can be manually implemented. For example, `__assert_defined__` may be implemented as:

```typescript
function __assert_defined__(obj) {
    if (typeof obj == "undefined") {
        throw "undefined"
    }
} 
```

## Known Issues
- Slow. Very slow. Largely caused by two things: Panda Assembly parsing and copy propagation, both of which are badly written.
- Limited coverage of the instruction set
- Loop structures are not recovered
- No support for `try-catch` structures

## Acknowledgements
dayu wasn't built in a day. It's the product of strenuous endeavor (plus many cups of bubble tea), and it can't go without help from others. We thank them for what they've done and continue to do:
- [Static Program Analysis](https://www.bilibili.com/video/BV1b7411K7P4/), Nanjing University, taught by Professors Yue Li and Tian Tan
- *Compilers: Principles, Techniques, and Tools, Second Edition* by Alfred V. Aho, Monica S. Lam, Ravi Sethi and Jeffrey D. Ullman
- [CS447 Compiler Theory](https://www.csd.uwo.ca/~mmorenom//CS447/Lectures/CodeOptimization.html/index.html), University of Western Ontario, taught by Professor Marc Moreno Maza
- [Lecture Notes on Decompilation](https://www.cs.cmu.edu/~fp/courses/15411-f13/lectures/20-decompilation.pdf) from 15-411 Compiler Design, Carnegie Mellon University, course by Professor Frank Pfenning, notes by Max Serrano

## License
GNU AGPL v3.0
