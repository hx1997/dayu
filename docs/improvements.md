# Planned Improvements

This document tracks known issues and improvement ideas for the next round of code upgrades, identified through a thorough review of the codebase in May 2026.

Status markers:
- Done: implemented and merged
- Partial: improved, but follow-up work remains
- Pending: not started yet

---

## Architecture & Design

### 1. Pass pipeline as data, not hardcode [Pending]
`decompiler.py` manually sequences every pass using long `if/elif` chains. A pass registry — an ordered list of `(Pass, level, args)` tuples — would make the pipeline declarative, easier to extend, and testable in isolation without touching the core decompiler logic.

### 2. Non-determinism in structural analysis (`random.choice`) [Done]
This issue has been fixed. `control_flow_structuring.py` no longer uses `random.choice` for region selection, so decompilation output is now deterministic for this pass.

### 3. Duplicated `find_dominators` and graph utility methods [Partial]
The duplicated dominator helpers shared by `control_flow_structuring.py` and `control_flow_structuring_old.py` have been extracted into `CFGUtils`, which removed the largest duplication in this area. Some small graph helper duplication still remains in other passes, so there is still room for consolidation.

### 4. Fixed-point convergence check uses instruction count [Pending]
In `llir_to_mlir`, the fixed-point check compares `method.count_insns()` before and after each iteration. Two structurally different programs can have the same instruction count, causing premature termination. Comparing a hash/snapshot of the instruction sequence, or tracking actual mutation flags within passes, would be more reliable.

---

## Missing Features

### 5. Exception / try-catch handling [Pending]
Multiple `FIXME` comments acknowledge that `throw`/try-catch structures are not properly analyzed. `BuildCFG` severs all edges from throw blocks rather than connecting them to their handlers. This causes silent, incorrect output for any method that uses exception handling — a very common pattern in real-world ArkTS apps.

### 6. Improper region handling in structural analysis [Pending]
The `# FIXME: handle Improper regions` comment in `control_flow_structuring.py` means any method with an irreducible CFG will fail silently and fall back to unstructured output. The standard approach is to insert explicit `goto` statements for severed back-edges and continue the reduction algorithm.

### 7. `for` loop and `switch/case` recovery [Pending]
`RegionType.Case` is defined in the enum but never matched or reduced anywhere. `for` loops (extremely common in ArkTS/TypeScript) are also not recovered — only `while` loops and `if/else` are handled. This results in verbose `while (true)` constructs with internal `break` statements where a clean `for` loop could be emitted instead.

### 8. `poplexenv` instructions not erased from output [Pending]
The existing FIXME in `resolve_lexvar.py` acknowledges that `poplexenv` instructions remain in the final pseudocode, reducing readability. The noted obstacle (label-preservation) is solvable by transferring the instruction's label to the immediately preceding instruction before erasure.

---

## Code Quality

### 9. Two competing control flow structuring implementations [Pending]
`control_flow_structuring_old.py` and `control_flow_structuring.py` coexist, with a runtime config switch to choose between them. Both are being maintained in parallel, doubling the cost of any control flow fix. The old implementation should either be deleted once the new one reaches parity, or clearly marked as a fallback with documented known differences.

### 10. `NAddressCode.__str__` is a monolithic 40-line `if/elif` chain [Pending]
The `__str__` method handles every NAC type in a single long conditional block. Splitting this into per-type `format_*` methods (or a visitor pattern) would make it easier to add new NAC types or modify formatting without risking regressions in unrelated branches.

### 11. `RawIR2LLIR` creates an orphaned `IRModule` internally [Done]
This issue has been fixed. `RawIR2LLIR` now builds with the method's real parent module instead of creating an unrelated `IRModule()` instance.

### 12. Silent `None` return when target method/class is not found [Done]
This issue has been fixed. `Decompiler.decompile()` now raises clear exceptions when the requested class or method cannot be found.

---

## Output & Usability

### 13. No file output option [Done]
This issue has been fixed. The CLI now supports `-o` / `--output-file`, which redirects printed output to a file instead of stdout.

### 14. No structured / machine-readable output mode [Pending]
`PrintPcode` only calls `print()`. Adding a JSON or AST serialization output mode would allow downstream tooling (syntax highlighters, diff tools, further static analysis) to consume decompilation results without fragile regex-parsing of printed text.

### 15. CFG output path not sanitized [Done]
This issue has been fixed. CFG output paths are now sanitized before being passed to graphviz, so method names with special characters no longer produce invalid filenames.

---

## Testing & Robustness

### 16. No test suite [Pending]
There are no tests in the repository. Given the complexity of the multi-stage IR pipeline, even a small set of golden-output tests (input `.abc` + expected pseudocode) would catch regressions when passes are modified. The `examples/` directory already contains suitable sample files.

### 17. Dataflow analyses rebuild state from scratch on every call [Pending]
Both `ReachingDefinitions` and `CopyPropagation` iterate over all blocks and instructions to build their initial sets at the start of every invocation. Since these analyses are called repeatedly in the MLIR fixed-point loop, incremental invalidation — re-analyzing only blocks whose predecessors changed — could significantly speed up decompilation of large methods.
