# Under the Hood - how dayu works
The dayu decompiler works by first translating the bytecode into an intermediate representation (IR), and then translating the IR into pseudocode. This process consists of several stages, as shown in the following diagram.

![](imgs/decompiler_workflow.png)

## Stage 1: Bytecode to Raw IR
This stage simply parses Panda Assembly, extract bytecode instructions, and put them into dayu's internal structures (e.g., an `NAddressCode` for each instruction). Subsequent analysis and translation will be performed on these internal structures only.

## Stage 2: Raw IR to LLIR
In this stage, we build the Control Flow Graph (CFG) based on Raw IR, and lift Raw IR to LLIR. We aim to represent the operations of the original bytecode with a restricted and standardized set of IR instructions.

The process of translating from a lower-level language to a higher-level one is known as *lifting*. We write a lifter method for each Ark opcode, in which we determine which type of LLIR instruction this should be (e.g., an assignment, or an unconditional jump) and what arguments it has. Then we replace the Raw IR instruction with an LLIR one/LLIR ones created using said information. One Raw IR instruction may translate into multiple LLIR instructions if its operation is complex (e.g., requiring pseudo-functions).

LLIR and MLIR instructions are something like the Three-Address Code (TAC), except that function calls may have more than three arguments. Therefore, they are called `NAddressCode`s or NACs instead.

(to be continued)