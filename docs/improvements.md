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

### 10. `NAddressCode` typed subclass hierarchy [Done]
`NAddressCode` has been refactored into 10 typed subclasses (`AssignNAC`, `CallNAC`, `UncondJumpNAC`, `CondJumpNAC`, `ReturnNAC`, `UncondThrowNAC`, `CondThrowNAC`, `ImportNAC`, `VarDeclNAC`, `UnknownNAC`) under a common `NACBase`. Each subclass uses named fields (`dst`, `src`, `src2`, `func`, `call_args`, etc.) instead of positional `args` indexing. The `NAddressCode()` factory function is preserved for backwards compatibility. All passes have been updated to use named fields where the type is known. `__str__` is now implemented as a per-subclass `__str__` method, eliminating the monolithic `if/elif` chain.

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

### 16. No test suite [Done]
This issue has been fixed. The repository now has a `unittest`-based regression suite under `tests/`, built around the bundled example inputs in `examples/`. Coverage now includes golden decompilation checks across both bundled datasets, CLI output-file handling, bundled input loading, the missing-method error path, and small parser/dataflow unit tests.

### 17. Dataflow analyses rebuild state from scratch on every call [Pending]
Both `ReachingDefinitions` and `CopyPropagation` iterate over all blocks and instructions to build their initial sets at the start of every invocation. Since these analyses are called repeatedly in the MLIR fixed-point loop, incremental invalidation — re-analyzing only blocks whose predecessors changed — could significantly speed up decompilation of large methods.

---

## Output Readability

### 18. Residual `jump_label_X:` labels in structured output [Pending]
`print_pcode.py` still emits labels that were already consumed by control flow structuring (e.g. the loop-entry and loop-exit labels surrounding a `while` block). These should be suppressed when the label's only use is as the target of the structured construct that wraps it.

### 19. `__ToNumeric__` in loop increment expressions [Pending]
The VM emits `tonumeric` before every arithmetic operation. This lifts as a `CallNAC` (`v1 = __ToNumeric__(v0)`), which copy propagation cannot fold (CALL results are excluded). A peephole rule that folds `v = __ToNumeric__(x)` → `v = x` when `x` is provably numeric (defined by a numeric literal or arithmetic ASSIGN) would eliminate the redundant temp variable from loop increments.

### 20. `__is_hole__` / `throw 'Value of ... is undefined'` boilerplate [Pending]
Every imported symbol is guarded by a compiler-generated null check that emits three lines of pseudocode. These groups could be hoisted out of loop bodies and optionally suppressed in the output, since they are boilerplate not present in the original TypeScript source.

### 21. `CallNAC` result assigned to variable immediately overwritten [Pending]
When a call's return value is stored in a variable that is immediately overwritten before any use (e.g. `v2 = hilog.info(...); v2 = __ToNumeric__(v0)`), the first assignment should be emitted as a void call. Dead code elimination handles ASSIGN dead results but not CALL.

### 22. Small integer hex literals should display as decimal [Pending]
Literals like `0x0`, `0x1`, `0x4`, `0x5` are emitted in hex. A formatting pass in `print_pcode.py` that converts small integers (e.g. `abs(x) < 256`) to decimal would improve readability.

### 23. `for` loop synthesis from `while` + counter init [Pending]
The pattern `v = 0; while (v < N) { ...; v = v + 1 }` is a canonical `for` loop. Control flow structuring (or a post-pass over the emitted pseudocode) could detect and emit `for (let v = 0; v < N; v++)` instead.

### 24. `CallNAC` falling through to ASSIGN-only peephole cases [Done]
In unconstrained mode, `CallNAC` instructions were not guarded before cases 1–5 in `eliminate_redundant_load_store`, which all access `.src` (an `AssignNAC`-only field). An explicit `continue` guard for `CALL` was added after the type filter.
