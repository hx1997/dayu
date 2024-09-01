[简体中文](how_it_works_zh_simp.md) | **English**

# Under the Hood - how dayu works
The dayu decompiler works by first translating the bytecode into an intermediate representation (IR), and then translating the IR into pseudocode. This process consists of several stages, as shown in the following diagram.

![](imgs/decompiler_workflow.png)

## Stage 1: Bytecode to Raw IR
This stage simply parses Panda Assembly, extracts bytecode instructions, and puts them into dayu's internal structures (e.g., an `NAddressCode` for each instruction). Subsequent analysis and translation will be performed on these internal structures only.

## Stage 2: Raw IR to LLIR
In this stage, we build the Control Flow Graph (CFG) based on Raw IR, and lift Raw IR to LLIR. We aim to represent the operations of the original bytecode with a restricted and standardized set of IR instructions. This unified form facilitates analysis and decompilation.

The process of translating from a lower-level language to a higher-level one is known as *lifting*. We write a lifter method for each Ark opcode, in which we determine which type of LLIR instruction this should be (e.g., an assignment, or an unconditional jump) and what arguments it has. Then we replace the Raw IR instruction with an LLIR one/LLIR ones created using said information. One Raw IR instruction may translate into multiple LLIR instructions if its operation is complex (e.g., requiring pseudo-functions).

LLIR and MLIR instructions are something like the Three-Address Code (TAC), except that function calls may have more than three arguments. Therefore, they are called `NAddressCode`s or NACs instead.

At the time of writing, there are eight types of NACs:
- ASSIGN: assignment statements, takes at most three arguments
- UNCOND_JUMP: unconditional jump statements, takes exactly one argument
- COND_JUMP: conditional jump statements, takes exactly three arguments
- CALL: function/method call statements, takes at least one argument (the function/method name)
- RETURN: return statements, takes exactly one argument
- UNCOND_THROW: unconditional throw statements, takes exactly one argument
- COND_THROW: conditional throw statements, takes exactly three arguments
- UNKNOWN: reserved for code that is not "proper" IR (not having their `NAddressCode` fields properly set up), e.g. Raw IR or pseudocode, sometimes HLIR too

In the lifter methods, Raw IR will be converted to LLIR that consists of NACs of these types only. For example, a Raw IR instruction `lda v2` (assign `v2` to `acc`) will become a NAC of `ASSIGN` type, with arguments `acc` and `v2`.

(to be continued)