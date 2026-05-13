# NAC Type Hierarchy Refactor Plan

## Goal
Split the single `NAddressCode` class into 10 typed subclasses, each with meaningful named fields
instead of the positional `self.args` list. This eliminates the ambiguous encoding where
`args[0]` means "dst", "target", "cond1", or "exception" depending on the type.

## New Class Hierarchy

```
NACBase
├── AssignNAC        (ASSIGN)
├── UncondJumpNAC    (UNCOND_JUMP)
├── CondJumpNAC      (COND_JUMP)
├── CallNAC          (CALL)
├── ReturnNAC        (RETURN)
├── UncondThrowNAC   (UNCOND_THROW)
├── CondThrowNAC     (COND_THROW)
├── ImportNAC        (IMPORT)
├── VarDeclNAC       (VAR_DECL)
└── UnknownNAC       (UNKNOWN)   ← keeps real mutable args list permanently
```

`NAddressCode` becomes a factory function with the original signature so no call sites
break before they are explicitly migrated.

## Field Mapping

| Class           | Named fields                          | `args` property                           |
|-----------------|---------------------------------------|-------------------------------------------|
| `AssignNAC`     | `dst, src, op, src2=None`             | `[dst, src]` or `[dst, src, src2]`        |
| `UncondJumpNAC` | `target`                              | `[target]`                                |
| `CondJumpNAC`   | `cond1, op, cond2=None, target`       | `[cond1, target]` or `[cond1, cond2, target]` |
| `CallNAC`       | `dst, func, call_args`                | `[dst, func, *call_args]`                 |
| `ReturnNAC`     | `retval`                              | `[retval]`                                |
| `UncondThrowNAC`| `exception`                           | `[exception]`                             |
| `CondThrowNAC`  | `cond1, op, cond2, exception`         | `[cond1, cond2, exception]`               |
| `ImportNAC`     | `imported, local_name, module`        | `[imported, local_name, module]`          |
| `VarDeclNAC`    | `var_names`                           | `[*var_names]`                            |
| `UnknownNAC`    | `op, args`                            | real mutable list (no property)           |

The `.args` property on typed subclasses is **read-only** (returns a fresh list of references).
This is sufficient for iteration-only passes (`var_alloc`, `prop_access_prettify`) that
mutate arg objects in-place (.type, .value) but never replace list slots.

## Methods on NACBase

```python
get_defs() -> list          # instruction-level write targets
get_uses() -> list          # instruction-level reads, including dst.ref_obj, ExprArg expansion
replace_var_use(copy_, constrained) -> bool  # typed slot replacement for copy_propagation
remap_args(fn)              # apply fn to every arg, replacing it — for resolve_lexvar
is_relational_operation() -> bool   # default False; overridden on Assign/CondJump/CondThrow
invert_relational_operation() -> bool
erase_from_parent()
format_nac_str_with_label(s) -> str
__str__()
```

### get_defs / get_uses semantics
- `get_defs()` returns `[dst]` for defining instructions (AssignNAC, CallNAC); `[]` otherwise.
- `get_uses()` includes:
  - All source args
  - `dst.ref_obj` when set (e.g. `v0['x'] = v1` — v0 is used as a base)
  - `ref_obj` on source args
  - Nested ExprArg expansion via `arg.get_used_args()`
- Block-level def/use ordering logic stays in `defuse.py` — these are instruction-level only.

### replace_var_use
Replaces uses of `copy_.dst` (the defined var of the copy) with `copy_.args[1:]`-equivalent.
Currently implemented as `CopyPropagation.replace_var_use(insn, copy_)`. After refactor,
each subclass owns this logic. Called from `CopyPropagation.replace_copies`.
Returns True if all uses were successfully replaced.

### remap_args(fn)
Applies `fn(arg) -> arg` to every arg the subclass owns. Used by
`ResolveLexVar.handle_lexvar_uses` instead of `insn.args = new_list`.
Each subclass applies fn to every named field (and elements of list fields like call_args/var_names).

## Key Migration Mappings

### copy_propagation.py
```
insn.args[idx] = x          →  insn.replace_var_use(copy_, constrained)
copy_.args[0]               →  copy_.dst
copy_.args[1:]              →  [copy_.src] or [copy_.src, copy_.src2] (AssignNAC)
                               [copy_.func, *copy_.call_args]         (CallNAC)
len(copy_.args) == 2        →  isinstance(copy_, AssignNAC) and copy_.src2 is None
len(copy_.args) >= 3        →  copy_.src2 is not None  (Assign)  or  isinstance(copy_, CallNAC)
copy_.args[1:]  ExprArg     →  get_uses() handles this
```

### defuse.py / dead_code.py
```
insn.type == X; insn.args[0]  →  insn.get_defs()[0]
insn.args[1], insn.args[2]    →  insn.get_uses()
```
Both files collapse from ~80 lines of per-type dispatch to a ~15-line loop over get_defs()/get_uses().

### reaching_def.py
```
definition.args[0]            →  definition.dst  (ASSIGN/CALL)
copy_.args[0]                 →  copy_.dst
copy_.args[1:]                →  named fields or get_uses()
len(insn.args) == 2           →  src2 is None
copy_.args[2:]                →  call_args  (CALL)
```

### peephole_opt.py
```
insn.args[0]  (ASSIGN)        →  insn.dst
insn.args[1]  (ASSIGN)        →  insn.src
insn.args[2]  (ASSIGN)        →  insn.src2
insn.args[0]  (COND_JUMP/THROW) → insn.cond1
insn.args[1]  (COND_JUMP/THROW) → insn.cond2
insn.args[2]  (COND_JUMP/THROW) → insn.target / insn.exception
insn.args[0]  (CALL)          →  insn.dst
insn.args[1]  (CALL)          →  insn.func
insn.args[3]  (CALL)          →  insn.call_args[1]
```

### method_call_prettify.py
```
insn.args[2:]  = insn.args[4:]   →  insn.call_args = insn.call_args[2:]
insn.args[2].type                →  insn.call_args[0].type
insn.args[3].type                →  insn.call_args[1].type
len(insn.args) < 4               →  len(insn.call_args) < 2
```

### resolve_lexvar.py
```
insn.args = new_list             →  insn.remap_args(fn)
insn.args[i] = x  (VarDecl)     →  insn.var_names[i] = x
insn.args[0]  (CALL)            →  insn.dst
insn.args[1]  (CALL)            →  insn.func
insn.args[2]  (CALL, lifted defineclasswithbuffer) → insn.call_args[0]
insn.args[0]  (VAR_DECL)        →  insn.var_names[0]
insn.args[1].value  (UNKNOWN)   →  insn.args[1].value  (unchanged, raw IR)
insn.extra_info[...]             →  unchanged (on NACBase)
```

### control_flow_structuring.py
```
NAddressCode(text, [], UNKNOWN, ...) →  UnknownNAC(text, [], ...)
cond_jump_insn.args[0]           →  cond_jump_insn.cond1
cond_jump_insn.args[1]           →  cond_jump_insn.cond2
insn.args[0].value  (UNCOND_JUMP) → insn.target.value
insn.type is NAddressCodeType.UNCOND_JUMP → isinstance(insn, UncondJumpNAC)
```

### var_alloc.py
```
for arg in insn.args:            →  unchanged (works via .args property)
NAddressCode(s, [], UNKNOWN)     →  UnknownNAC(s, [])
```

### builder.py
```
NAddressCode(op, [dst,src], ASSIGN, ...)        →  AssignNAC(op=op, dst=dst, src=src, ...)
NAddressCode('', [target], UNCOND_JUMP, ...)    →  UncondJumpNAC(target=target, ...)
NAddressCode(rop, [c1,c2,t], COND_JUMP, ...)   →  CondJumpNAC(op=rop, cond1=c1, cond2=c2, target=t, ...)
NAddressCode('', [dst,func,*a], CALL, ...)      →  CallNAC(dst=dst, func=func, call_args=a, ...)
NAddressCode('', [retval], RETURN, ...)         →  ReturnNAC(retval=retval, ...)
NAddressCode('', [exc], UNCOND_THROW, ...)      →  UncondThrowNAC(exception=exc, ...)
NAddressCode(rop,[c1,c2,exc],COND_THROW,...)    →  CondThrowNAC(op=rop,cond1=c1,cond2=c2,exception=exc,...)
NAddressCode('', [imp,loc,mod], IMPORT, ...)    →  ImportNAC(imported=imp, local_name=loc, module=mod, ...)
NAddressCode('', var_names, VAR_DECL, ...)      →  VarDeclNAC(var_names=var_names, ...)
```

## Phases

| # | Files changed | Status |
|---|---------------|--------|
| 1 | `nac.py` — define full hierarchy + factory | [ ] |
| 2 | `builder.py` — typed constructors | [ ] |
| 3 | `defuse.py`, `dead_code.py` — use get_defs/get_uses | [ ] |
| 4 | `reaching_def.py`, `copy_propagation.py` | [ ] |
| 5 | `peephole_opt.py`, `method_call_prettify.py` | [ ] |
| 6 | `resolve_lexvar.py` | [ ] |
| 7 | `var_alloc.py`, `control_flow_structuring.py`, `pa2rawir.py` | [ ] |
| 8 | `dataflow_example.py`, `tests/` | [ ] |
| 9 | Drop `.args` property from typed subclasses | [ ] |

Run `python -m unittest discover -s tests` between each phase.
Each phase = one commit: `refactor: <description>`.

## Notes
- Raw IR instructions in `insn_lifter.py` receive `UnknownNAC` from `pa2rawir.py`.
  They access operands via `.args[n]` which is kept as a real mutable list on `UnknownNAC`.
  No changes needed in `insn_lifter.py`.
- `live_variable.py` uses `block.defs` / `block.uses` set by `defuse.py`. No direct NAC arg access.
  No changes needed.
- `print_pcode.py` and `viewcfg.py` use `str(insn)` only. No changes needed.
- The uncommitted formatter extraction (`_format_*` methods, `test_nac_formatting.py`) is
  superseded by this refactor. Each subclass gets its own `__str__`. Those changes will be
  discarded and replaced cleanly.
