#!/usr/bin/env python3
"""
Example demonstrating the dataflow analysis module's input and output

This example shows how to manually construct IR and run dataflow analysis passes
to understand their inputs and outputs.
"""

import sys
import os

from decompile.ir.basicblock import IRBlock
from decompile.ir.method import IRMethod
from decompile.ir.nac import NAddressCode, NAddressCodeType
from decompile.passes.defuse import DefUseAnalysis
from decompile.passes.reaching_def import ReachingDefinitions
from decompile.passes.live_variable import LiveVariableAnalysis
from pandasm.insn import PandasmInsnArgument


def create_example_method():
    """
    Create a simple method with IR for demonstration:
    
    Block 0:
        v0 = 5
        v1 = v0
        
    Block 1:  
        v2 = v1 + 10
        if v2 > 15 jump Block 3
        
    Block 2:
        v1 = 20
        jump Block 3
        
    Block 3:
        return v1
    """
    method = IRMethod("example_method")
    
    # Create basic blocks
    block0 = IRBlock(method)
    block1 = IRBlock(method) 
    block2 = IRBlock(method)
    block3 = IRBlock(method)
    
    # Block 0: v0 = 5; v1 = v0
    v0 = PandasmInsnArgument('reg', 'v0')
    v1 = PandasmInsnArgument('reg', 'v1')
    v2 = PandasmInsnArgument('reg', 'v2')
    const5 = PandasmInsnArgument('imm', '5')
    const10 = PandasmInsnArgument('imm', '10')
    const15 = PandasmInsnArgument('imm', '15')
    const20 = PandasmInsnArgument('imm', '20')
    
    # v0 = 5
    insn1 = NAddressCode('=', [v0, const5], NAddressCodeType.ASSIGN)
    block0.insert_insn(insn1)
    
    # v1 = v0  
    insn2 = NAddressCode('=', [v1, v0], NAddressCodeType.ASSIGN)
    block0.insert_insn(insn2)
    
    # Block 1: v2 = v1 + 10; if v2 > 15 jump Block3
    insn3 = NAddressCode('+', [v2, v1, const10], NAddressCodeType.ASSIGN)
    block1.insert_insn(insn3)
    
    label_block3 = PandasmInsnArgument('label', 'label_block3')
    insn4 = NAddressCode('>', [v2, const15, label_block3], NAddressCodeType.COND_JUMP)
    block1.insert_insn(insn4)
    
    # Block 2: v1 = 20; jump Block3
    insn5 = NAddressCode('=', [v1, const20], NAddressCodeType.ASSIGN)
    block2.insert_insn(insn5)
    
    insn6 = NAddressCode('jump', [label_block3], NAddressCodeType.UNCOND_JUMP)
    block2.insert_insn(insn6)
    
    # Block 3: return v1
    insn7 = NAddressCode('return', [v1], NAddressCodeType.RETURN)
    insn7.label = 'label_block3'  # Set the label for this instruction
    block3.insert_insn(insn7)
    
    # Set up control flow
    block0.add_successor(block1)
    block1.add_successor(block2)  # false branch
    block1.add_successor(block3)  # true branch
    block2.add_successor(block3)
    
    return method


def analyze_dataflow():
    """Run all dataflow analyses and print results"""
    method = create_example_method()
    
    print("=== DATAFLOW ANALYSIS EXAMPLE ===\n")
    print("Method structure:")
    for i, block in enumerate(method.blocks):
        print(f"Block {i}:")
        for insn in block.insns:
            print(f"  {insn.op} {[str(arg) for arg in insn.args]}")
        print(f"  Successors: {[method.blocks.index(s) for s in block.successors]}")
        print()
    
    # 1. Def-Use Analysis
    print("=== 1. DEF-USE ANALYSIS ===")
    defuse = DefUseAnalysis()
    defuse.run_on_method(method)
    
    print("Input: IRMethod with basic blocks and instructions")
    print("Output: defs and uses sets populated on each block\n")
    
    for i, block in enumerate(method.blocks):
        print(f"Block {i}:")
        print(f"  DEFS: {[str(d) for d in block.defs]}")
        print(f"  USES: {[str(u) for u in block.uses]}")
        print()
    
    # 2. Reaching Definitions
    print("=== 2. REACHING DEFINITIONS ANALYSIS ===")
    reaching_def = ReachingDefinitions()
    in_r, out_r = reaching_def.run_on_method(method)
    
    print("Input: IRMethod with control flow graph")
    print("Output: (in_block, out_block) dictionaries\n")
    
    for i, block in enumerate(method.blocks):
        print(f"Block {i}:")
        in_defs = [f"{d.op} {[str(arg) for arg in d.args]}" for d in in_r.get(block, set())]
        out_defs = [f"{d.op} {[str(arg) for arg in d.args]}" for d in out_r.get(block, set())]
        print(f"  IN:  {in_defs}")
        print(f"  OUT: {out_defs}")
        print()
    
    # 3. Live Variable Analysis  
    print("=== 3. LIVE VARIABLE ANALYSIS ===")
    live_var = LiveVariableAnalysis()
    in_l, out_l = live_var.run_on_method(method)
    
    print("Input: IRMethod with defs/uses sets populated")
    print("Output: (in_block, out_block) dictionaries\n")
    
    for i, block in enumerate(method.blocks):
        print(f"Block {i}:")
        in_vars = [str(v) for v in in_l.get(block, set())]
        out_vars = [str(v) for v in out_l.get(block, set())]
        print(f"  IN:  {in_vars}")
        print(f"  OUT: {out_vars}")
        print()
    
    return method, (in_r, out_r), (in_l, out_l)


if __name__ == "__main__":
    analyze_dataflow()