# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview
dayu is a parser and decompiler for .abc files (Ark Bytecode files) used on Open/HarmonyOS. It analyzes and reverse-engineers compiled ArkTS/TypeScript applications back into readable pseudocode.

## Running the Tool

### Command Line Usage
```bash
# Install dependencies
pip install -r requirements.txt

# Basic decompilation workflow (requires both .abc and disassembled .txt files)
python main.py -abc input.abc -pa input.txt -dme "com.example.Class.method"

# List all classes
python main.py -pa input.txt -pc

# List methods in a specific class  
python main.py -pa input.txt -pmc "com.example.Class"

# Decompile entire class
python main.py -abc input.abc -pa input.txt -dc "com.example.Class"

# View Control Flow Graph (requires graphviz)
python main.py -abc input.abc -pa input.txt -dme "com.example.Class.method" -cfg

# Different output levels: llir, mlir, hlir, pcode (default)
python main.py -abc input.abc -pa input.txt -dme "com.example.Class.method" -O hlir
```

### Preprocessing Requirements
Before decompiling, you need to disassemble the .abc file using HarmonyOS SDK:
```bash
ark_disasm input.abc input.txt
```

## Architecture Overview

### High-Level Design
The decompiler follows a multi-stage IR transformation pipeline:
1. **Bytecode → Raw IR**: Parse Panda Assembly into internal structures
2. **Raw IR → LLIR**: Build CFG and lift to Low-Level IR using standardized NAddressCode (NAC) instructions  
3. **LLIR → MLIR**: Apply optimization passes (copy propagation, dead code elimination, etc.)
4. **MLIR → HLIR**: Further optimizations and control flow recovery
5. **HLIR → Pseudocode**: Generate final human-readable code

### Core Module Structure

#### `ark/` - ABC File Parsing
- `abcreader.py`: Main entry point for reading .abc files
- `abcfile/`: Version-specific parsers (ABC v9, v12)
- `abcclass/`, `abcfield/`, `abcmethod/`: Structure parsers for classes, fields, methods
- `abcstring.py`, `abcliteralarray/`: String and literal handling

#### `pandasm/` - Panda Assembly Parsing  
- `reader.py`: Main entry point for parsing disassembled text files
- `file.py`, `pa_class.py`, `method.py`: Structure representations
- `insn.py`: Instruction parsing and representation

#### `decompile/` - Core Decompilation Engine
- `decompiler.py`: Main decompiler orchestrating the pipeline
- `config.py`: Configuration classes (DecompilerConfig, output levels, granularity)
- `pa2rawir.py`: Converts Panda Assembly to Raw IR

#### `decompile/ir/` - Intermediate Representation
- `nac.py`: NAddressCode definitions (ASSIGN, CALL, JUMP, etc.)
- `basicblock.py`: Control flow graph basic blocks
- `method.py`, `irclass.py`, `module.py`: IR structure containers
- `builder.py`: IR instruction builder utilities
- `insn_lifter.py`: Lifts bytecode instructions to IR

#### `decompile/passes/` - Analysis and Optimization Passes
- `rawir2llir.py`: Raw IR to LLIR transformation
- `buildcfg.py`: Control Flow Graph construction
- `copy_propagation.py`, `dead_code.py`: Standard optimizations
- `control_flow_structuring.py`: Recovers high-level control structures (if/while/for)
- `resolve_lexvar.py`: Resolves lexical variable references
- `print_pcode.py`: Final pseudocode generation

### Key Data Structures

#### NAddressCode (NAC) Types
- `ASSIGN`: Variable assignments (max 3 operands)
- `CALL`: Function/method calls (1+ operands)  
- `UNCOND_JUMP`/`COND_JUMP`: Control flow transfers
- `RETURN`: Method returns
- `UNCOND_THROW`/`COND_THROW`: Exception handling

#### Decompilation Granularity
- `METHOD`: Single method decompilation
- `CLASS`: All methods in a class
- `MODULE`: Entire file

#### Output Levels
- `LOW_LEVEL_IR`: Basic lifted bytecode
- `MEDIUM_LEVEL_IR`: After initial optimizations
- `HIGH_LEVEL_IR`: After advanced optimizations
- `PSEUDOCODE`: Final human-readable output

## Development Guidelines

### File Structure Conventions
- Each major component has its own directory (`ark/`, `pandasm/`, `decompile/`)
- Version-specific implementations use suffixes (`abcfile9.py`, `abcfile12.py`)
- Pass implementations go in `decompile/passes/`

### Adding New Bytecode Instructions
1. Add opcode to `decompile/isa.json` 
2. Implement lifter in `decompile/ir/insn_lifter.py`
3. Update instruction enum in `decompile/ir/insn_enum.py`

### Adding Optimization Passes
1. Inherit from appropriate base class (`MethodPass`, `ClassPass`, `ModulePass`)
2. Place in `decompile/passes/`
3. Register in decompiler pipeline in `decompiler.py`

### Configuration
Decompiler behavior is controlled via `DecompilerConfig`:
- Enable/disable specific optimization passes
- Control number of pass iterations (-1 = run to fixed point)
- Toggle control flow recovery algorithms
- Set variable renaming and method call prettification