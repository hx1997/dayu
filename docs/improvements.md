# Planned Improvements

This document tracks known issues and improvement ideas for the next round of code upgrades, identified through a thorough review of the codebase in May 2026.

---

## Architecture & Design

### 1. Pass pipeline as data, not hardcode
`decompiler.py` manually sequences every pass using long `if/elif` chains. A pass registry — an ordered list of `(Pass, level, args)` tuples — would make the pipeline declarative, easier to extend, and testable in isolation without touching the core decompiler logic.

### 2. Non-determinism in structural analysis (`random.choice`)
`control_flow_structuring.py` uses `random.choice` when iterating over successors/predecessors during `acyclic_region_type`. This makes decompilation output **non-deterministic across runs**, which is a correctness issue. The selection should be made deterministically using post-order numbering, which is already computed and available in the same pass.

### 3. Duplicated `find_dominators` and graph utility methods
Identical implementations of `find_dominators`, `is_no_predecessor_block`, and `is_no_successor_block` exist in both `control_flow_structuring.py` and `control_flow_structuring_old.py`, and `is_no_successor_block` is also copied across several other passes. These should be extracted into a shared `CFGUtils` module, eliminating ~100 lines of duplication.

### 4. Fixed-point convergence check uses instruction count
In `llir_to_mlir`, the fixed-point check compares `method.count_insns()` before and after each iteration. Two structurally different programs can have the same instruction count, causing premature termination. Comparing a hash/snapshot of the instruction sequence, or tracking actual mutation flags within passes, would be more reliable.

---

## Missing Features

### 5. Exception / try-catch handling
Multiple `FIXME` comments acknowledge that `throw`/try-catch structures are not properly analyzed. `BuildCFG` severs all edges from throw blocks rather than connecting them to their handlers. This causes silent, incorrect output for any method that uses exception handling — a very common pattern in real-world ArkTS apps.

### 6. Improper region handling in structural analysis
The `# FIXME: handle Improper regions` comment in `control_flow_structuring.py` means any method with an irreducible CFG will fail silently and fall back to unstructured output. The standard approach is to insert explicit `goto` statements for severed back-edges and continue the reduction algorithm.

### 7. `for` loop and `switch/case` recovery
`RegionType.Case` is defined in the enum but never matched or reduced anywhere. `for` loops (extremely common in ArkTS/TypeScript) are also not recovered — only `while` loops and `if/else` are handled. This results in verbose `while (true)` constructs with internal `break` statements where a clean `for` loop could be emitted instead.

### 8. `poplexenv` instructions not erased from output
The existing FIXME in `resolve_lexvar.py` acknowledges that `poplexenv` instructions remain in the final pseudocode, reducing readability. The noted obstacle (label-preservation) is solvable by transferring the instruction's label to the immediately preceding instruction before erasure.

---

## Code Quality

### 9. Two competing control flow structuring implementations
`control_flow_structuring_old.py` and `control_flow_structuring.py` coexist, with a runtime config switch to choose between them. Both are being maintained in parallel, doubling the cost of any control flow fix. The old implementation should either be deleted once the new one reaches parity, or clearly marked as a fallback with documented known differences.

### 10. `NAddressCode.__str__` is a monolithic 40-line `if/elif` chain
The `__str__` method handles every NAC type in a single long conditional block. Splitting this into per-type `format_*` methods (or a visitor pattern) would make it easier to add new NAC types or modify formatting without risking regressions in unrelated branches.

### 11. `RawIR2LLIR` creates an orphaned `IRModule` internally
The pass constructs its own `IRModule()` and uses it only as a builder context, while the method being lifted belongs to a different module. This is confusing and could cause subtle bugs if the builder ever uses module-level state. The builder should receive the method's actual parent module.

### 12. Silent `None` return when target method/class is not found
In `Decompiler.decompile()`, if the target class or method is not found, the loop simply ends and `None` is returned silently. This should raise a descriptive exception or at minimum log a clear error so the user knows the specified target doesn't exist.

---

## Output & Usability

### 13. No file output option
There is no `-o` / `--output-file` CLI argument. Decompiling an entire class sends everything to stdout, mixed with any warnings from the logger. Adding a file output option and ensuring log output is always directed to stderr (not stdout) would make the tool usable in shell pipelines.

### 14. No structured / machine-readable output mode
`PrintPcode` only calls `print()`. Adding a JSON or AST serialization output mode would allow downstream tooling (syntax highlighters, diff tools, further static analysis) to consume decompilation results without fragile regex-parsing of printed text.

### 15. CFG output path not sanitized
`cfg/cfg_{method.name}` can produce invalid filenames when method names contain characters like `/`, `:`, or spaces — which is common in fully-qualified ArkTS method names. The output path should be sanitized before being passed to graphviz.

---

## Testing & Robustness

### 16. No test suite
There are no tests in the repository. Given the complexity of the multi-stage IR pipeline, even a small set of golden-output tests (input `.abc` + expected pseudocode) would catch regressions when passes are modified. The `examples/` directory already contains suitable sample files.

### 17. Dataflow analyses rebuild state from scratch on every call
Both `ReachingDefinitions` and `CopyPropagation` iterate over all blocks and instructions to build their initial sets at the start of every invocation. Since these analyses are called repeatedly in the MLIR fixed-point loop, incremental invalidation — re-analyzing only blocks whose predecessors changed — could significantly speed up decompilation of large methods.
