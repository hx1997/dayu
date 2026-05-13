from enum import IntEnum, auto


class NAddressCodeType(IntEnum):
    """
    NACs can take on one of several forms:
        (1) x = y bop z
        (2) x = uop y
        (3) x = y
        (4) jump L
        (5) if x rop y jump L
        (6) x = y(z1, z2, ...)
        (7) return x
        (8) throw x
        (9) if x rop y throw y
        (10) import x as y from z
        (11) let x
    (1)-(3) are ASSIGN type, (4), UNCOND_JUMP type, (5), COND_JUMP type, (6), CALL type, (7), RETURN type,
    (8), UNCOND_THROW type, (9), COND_THROW type, (10), IMPORT type, and (11), VAR_DECL type;
    anything else (e.g., raw IR instructions) is UNKNOWN type.
    """
    ASSIGN = auto()
    UNCOND_JUMP = auto()
    COND_JUMP = auto()
    CALL = auto()
    RETURN = auto()
    UNCOND_THROW = auto()
    COND_THROW = auto()
    IMPORT = auto()
    VAR_DECL = auto()
    UNKNOWN = auto()


_RELATIONAL_OPS = {
    '==': '!=',
    '!=': '==',
    '<': '>=',
    '>': '<=',
    '<=': '>',
    '>=': '<',
    '===': '!==',
    '!==': '===',
    'in': '',
    'instanceof': '',
}


class NACBase:
    """Base class for all NAC instruction types.

    Each typed subclass stores named fields as canonical storage
    (e.g. ``_dst``, ``_src``) and exposes both named-field properties
    and a read-only ``args`` computed property for backward-compatible
    iteration.  ``UnknownNAC`` is the sole exception — it keeps a real
    mutable ``args`` list permanently.
    """

    # Subclasses set this as a class-level constant.
    type: NAddressCodeType

    # Default operator (empty for types that don't use one).
    # Subclasses that actually use an operator override this in __init__.
    op = ''

    def __init__(self, parent_block=None, label_name='', comment='', extra_info=None):
        self.label = label_name
        self.comment = comment
        self.extra_info = extra_info
        self.parent_block = parent_block
        if self.parent_block:
            self.parent_block.insert_insn(self)

    # ------------------------------------------------------------------
    # Def / use interface (instruction-level)
    # ------------------------------------------------------------------

    @staticmethod
    def _arg_uses(arg):
        """Expand one arg into all variables it reads: itself, its ref_obj, and
        any variables nested inside an ExprArg."""
        uses = [arg]
        if arg.ref_obj:
            uses.append(arg.ref_obj)
        if hasattr(arg, 'get_used_args'):
            uses.extend(arg.get_used_args())
        return uses

    def get_defs(self):
        """Return the instruction-level list of defined (written) variables."""
        return []

    def get_uses(self):
        """Return the instruction-level list of used (read) variables,
        including ref_obj chains and ExprArg expansion."""
        return []

    # ------------------------------------------------------------------
    # Arg remapping (used by ResolveLexVar instead of insn.args = new_list)
    # ------------------------------------------------------------------

    def remap_args(self, fn):
        """Apply *fn(arg) -> arg* to every owned arg, replacing it in-place."""
        raise NotImplementedError

    def replace_arg(self, idx, value):
        """Replace the arg at position *idx* with *value*.
        Used by CopyPropagation instead of ``insn.args[idx] = value``."""
        raise NotImplementedError(f'{self.__class__.__name__}.replace_arg not implemented')

    # ------------------------------------------------------------------
    # Relational-operation helpers
    # ------------------------------------------------------------------

    def is_relational_operation(self):
        return False

    def invert_relational_operation(self):
        raise AssertionError(f'{self.__class__.__name__} is not a relational operation')

    # ------------------------------------------------------------------
    # Common utilities
    # ------------------------------------------------------------------

    def erase_from_parent(self):
        if not self.parent_block:
            raise Exception(f'{self.__class__.__name__}: this instruction has no parent')
        self.parent_block.remove_insn(self)

    def format_nac_str_with_label(self, nac_str):
        if self.label:
            if self.comment:
                return f'{self.label}:\n{nac_str}  /* {self.comment} */'
            else:
                return f'{self.label}:\n{nac_str}'
        elif self.comment:
            return f'{nac_str}  /* {self.comment} */'
        else:
            return nac_str

    def __str__(self):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Typed subclasses
# ---------------------------------------------------------------------------

class AssignNAC(NACBase):
    """x = src  /  x = op src  /  x = src op src2"""

    type = NAddressCodeType.ASSIGN

    def __init__(self, op, dst, src, src2=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self._dst = dst
        self._src = src
        self._src2 = src2

    # Computed args property (read-only view of canonical named fields)

    @property
    def args(self):
        if self._src2 is not None:
            return [self._dst, self._src, self._src2]
        return [self._dst, self._src]

    # Named-field properties

    @property
    def dst(self):
        return self._dst

    @dst.setter
    def dst(self, value):
        self._dst = value

    @property
    def src(self):
        return self._src

    @src.setter
    def src(self, value):
        self._src = value

    @property
    def src2(self):
        return self._src2

    @src2.setter
    def src2(self, value):
        self._src2 = value

    def get_defs(self):
        return [self._dst]

    def get_uses(self):
        uses = []
        if self._dst.ref_obj:
            uses.append(self._dst.ref_obj)
        uses.extend(self._arg_uses(self._src))
        if self._src2 is not None:
            uses.extend(self._arg_uses(self._src2))
        return uses

    def replace_arg(self, idx, value):
        if idx == 0:
            self._dst = value
        elif idx == 1:
            self._src = value
        elif idx == 2:
            self._src2 = value
        else:
            raise IndexError(f'AssignNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._dst = fn(self._dst)
        self._src = fn(self._src)
        if self._src2 is not None:
            self._src2 = fn(self._src2)

    def is_relational_operation(self):
        return self.op in _RELATIONAL_OPS

    def invert_relational_operation(self):
        assert self.is_relational_operation()
        inverted = _RELATIONAL_OPS[self.op]
        if inverted != '':
            self.op = inverted
            return True
        return False

    def __str__(self):
        if self._src2 is not None:
            s = f'{self._dst} = {self._src} {self.op} {self._src2}'
        else:
            s = f'{self._dst} = {self.op + (" " if self.op else "")}{self._src}'
        return self.format_nac_str_with_label(s)


class UncondJumpNAC(NACBase):
    """jump target"""

    type = NAddressCodeType.UNCOND_JUMP

    def __init__(self, target,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._target = target

    @property
    def args(self):
        return [self._target]

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        self._target = value

    def get_uses(self):
        return self._arg_uses(self._target)

    def replace_arg(self, idx, value):
        if idx == 0:
            self._target = value
        else:
            raise IndexError(f'UncondJumpNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._target = fn(self._target)

    def __str__(self):
        return self.format_nac_str_with_label(f'jump {self._target}')


class CondJumpNAC(NACBase):
    """if (cond1) jump target  /  if (cond1 op cond2) jump target"""

    type = NAddressCodeType.COND_JUMP

    def __init__(self, op, cond1, target, cond2=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self._cond1 = cond1
        self._cond2 = cond2
        self._target = target

    @property
    def args(self):
        if self._cond2 is not None:
            return [self._cond1, self._cond2, self._target]
        return [self._cond1, self._target]

    @property
    def cond1(self):
        return self._cond1

    @cond1.setter
    def cond1(self, value):
        self._cond1 = value

    @property
    def cond2(self):
        return self._cond2

    @cond2.setter
    def cond2(self, value):
        self._cond2 = value

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, value):
        self._target = value

    def get_uses(self):
        uses = self._arg_uses(self._cond1)
        if self._cond2 is not None:
            uses.extend(self._arg_uses(self._cond2))
        # target is a label; include it for behavioural consistency with the old defuse.py
        uses.extend(self._arg_uses(self._target))
        return uses

    def replace_arg(self, idx, value):
        if idx == 0:
            self._cond1 = value
        elif idx == 1:
            if self._cond2 is not None:
                self._cond2 = value
            else:
                self._target = value
        elif idx == 2:
            self._target = value
        else:
            raise IndexError(f'CondJumpNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._cond1 = fn(self._cond1)
        if self._cond2 is not None:
            self._cond2 = fn(self._cond2)
        self._target = fn(self._target)

    def is_relational_operation(self):
        return self.op in _RELATIONAL_OPS

    def invert_relational_operation(self):
        assert self.is_relational_operation()
        inverted = _RELATIONAL_OPS[self.op]
        if inverted != '':
            self.op = inverted
            return True
        return False

    def __str__(self):
        if self._cond2 is not None:
            s = f'if ({self._cond1} {self.op} {self._cond2}) jump {self._target}'
        else:
            s = f'if ({self._cond1}) jump {self._target}'
        return self.format_nac_str_with_label(s)


class CallNAC(NACBase):
    """dst = func(call_args...)"""

    type = NAddressCodeType.CALL

    def __init__(self, func, call_args, dst=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._dst = dst
        self._func = func
        self._call_args = list(call_args)

    @property
    def args(self):
        return [self._dst, self._func, *self._call_args]

    @property
    def dst(self):
        return self._dst

    @dst.setter
    def dst(self, value):
        self._dst = value

    @property
    def func(self):
        return self._func

    @func.setter
    def func(self, value):
        self._func = value

    @property
    def call_args(self):
        return self._call_args

    @call_args.setter
    def call_args(self, value):
        self._call_args = list(value)

    def get_defs(self):
        return [self._dst]

    def get_uses(self):
        uses = []
        if self._dst.ref_obj:
            uses.append(self._dst.ref_obj)
        uses.extend(self._arg_uses(self._func))
        for a in self._call_args:
            uses.extend(self._arg_uses(a))
        return uses

    def replace_arg(self, idx, value):
        if idx == 0:
            self._dst = value
        elif idx == 1:
            self._func = value
        else:
            self._call_args[idx - 2] = value

    def remap_args(self, fn):
        self._dst = fn(self._dst)
        self._func = fn(self._func)
        self._call_args = [fn(a) for a in self._call_args]

    def __str__(self):
        call_args_str = [str(a) for a in self._call_args]
        return self.format_nac_str_with_label(
            f'{self._dst} = {self._func}({", ".join(call_args_str)})'
        )


class ReturnNAC(NACBase):
    """return retval"""

    type = NAddressCodeType.RETURN

    def __init__(self, retval,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._retval = retval

    @property
    def args(self):
        return [self._retval]

    @property
    def retval(self):
        return self._retval

    @retval.setter
    def retval(self, value):
        self._retval = value

    def get_uses(self):
        return self._arg_uses(self._retval)

    def replace_arg(self, idx, value):
        if idx == 0:
            self._retval = value
        else:
            raise IndexError(f'ReturnNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._retval = fn(self._retval)

    def __str__(self):
        return self.format_nac_str_with_label(f'return {self._retval}')


class UncondThrowNAC(NACBase):
    """throw exception"""

    type = NAddressCodeType.UNCOND_THROW

    def __init__(self, exception,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._exception = exception

    @property
    def args(self):
        return [self._exception]

    @property
    def exception(self):
        return self._exception

    @exception.setter
    def exception(self, value):
        self._exception = value

    def get_uses(self):
        return self._arg_uses(self._exception)

    def replace_arg(self, idx, value):
        if idx == 0:
            self._exception = value
        else:
            raise IndexError(f'UncondThrowNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._exception = fn(self._exception)

    def __str__(self):
        return self.format_nac_str_with_label(f'throw {self._exception}')


class CondThrowNAC(NACBase):
    """if (cond1 op cond2) throw exception"""

    type = NAddressCodeType.COND_THROW

    def __init__(self, op, cond1, cond2, exception,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self._cond1 = cond1
        self._cond2 = cond2
        self._exception = exception

    @property
    def args(self):
        return [self._cond1, self._cond2, self._exception]

    @property
    def cond1(self):
        return self._cond1

    @cond1.setter
    def cond1(self, value):
        self._cond1 = value

    @property
    def cond2(self):
        return self._cond2

    @cond2.setter
    def cond2(self, value):
        self._cond2 = value

    @property
    def exception(self):
        return self._exception

    @exception.setter
    def exception(self, value):
        self._exception = value

    def get_uses(self):
        uses = []
        for a in [self._cond1, self._cond2, self._exception]:
            uses.extend(self._arg_uses(a))
        return uses

    def replace_arg(self, idx, value):
        if idx == 0:
            self._cond1 = value
        elif idx == 1:
            self._cond2 = value
        elif idx == 2:
            self._exception = value
        else:
            raise IndexError(f'CondThrowNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._cond1 = fn(self._cond1)
        self._cond2 = fn(self._cond2)
        self._exception = fn(self._exception)

    def is_relational_operation(self):
        return self.op in _RELATIONAL_OPS

    def invert_relational_operation(self):
        assert self.is_relational_operation()
        inverted = _RELATIONAL_OPS[self.op]
        if inverted != '':
            self.op = inverted
            return True
        return False

    def __str__(self):
        s = f'if ({self._cond1} {self.op} {self._cond2}) throw {self._exception}'
        return self.format_nac_str_with_label(s)


class ImportNAC(NACBase):
    """import { imported } as local_name from 'module'"""

    type = NAddressCodeType.IMPORT

    def __init__(self, imported, local_name, module,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._imported = imported
        self._local_name = local_name
        self._module = module

    @property
    def args(self):
        return [self._imported, self._local_name, self._module]

    @property
    def imported(self):
        return self._imported

    @imported.setter
    def imported(self, value):
        self._imported = value

    @property
    def local_name(self):
        return self._local_name

    @local_name.setter
    def local_name(self, value):
        self._local_name = value

    @property
    def module(self):
        return self._module

    @module.setter
    def module(self, value):
        self._module = value

    def replace_arg(self, idx, value):
        if idx == 0:
            self._imported = value
        elif idx == 1:
            self._local_name = value
        elif idx == 2:
            self._module = value
        else:
            raise IndexError(f'ImportNAC has no arg at index {idx}')

    def remap_args(self, fn):
        self._imported = fn(self._imported)
        self._local_name = fn(self._local_name)
        self._module = fn(self._module)

    def __str__(self):
        s = ('import { ' + f'{self._imported}' + ' } as '
             + f"{self._local_name} from '{self._module}';")
        return self.format_nac_str_with_label(s)


class VarDeclNAC(NACBase):
    """let var1, var2, ..."""

    type = NAddressCodeType.VAR_DECL

    def __init__(self, var_names,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self._var_names = list(var_names)

    @property
    def args(self):
        return list(self._var_names)

    @property
    def var_names(self):
        return self._var_names

    @var_names.setter
    def var_names(self, value):
        self._var_names = list(value)

    def replace_arg(self, idx, value):
        self._var_names[idx] = value

    def remap_args(self, fn):
        self._var_names = [fn(v) for v in self._var_names]

    def __str__(self):
        return self.format_nac_str_with_label(
            f'let {", ".join([str(a) for a in self._var_names])}'
        )


class UnknownNAC(NACBase):
    """Raw IR instruction or structured control-flow text (while {, }, etc.).
    Keeps a real mutable args list permanently — this is intentional since raw IR
    operands are inherently positional."""

    type = NAddressCodeType.UNKNOWN

    def __init__(self, op, args=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self.args = list(args) if args is not None else []

    def replace_arg(self, idx, value):
        self.args[idx] = value

    def remap_args(self, fn):
        for i in range(len(self.args)):
            self.args[i] = fn(self.args[i])

    def __str__(self):
        s = f'{self.op} {", ".join([str(a) for a in self.args])}'
        return self.format_nac_str_with_label(s)


# ---------------------------------------------------------------------------
# Factory function — keeps the original NAddressCode(...) call signature so
# all existing call sites continue to work without modification.
# ---------------------------------------------------------------------------

def NAddressCode(op, args=None, nac_type=NAddressCodeType.ASSIGN,
                 parent_block=None, label_name='', comment='', extra_info=None):
    """Create the appropriate NACBase subclass for the given nac_type."""
    args = args if args is not None else []
    kw = dict(parent_block=parent_block, label_name=label_name,
              comment=comment, extra_info=extra_info)

    if nac_type == NAddressCodeType.ASSIGN:
        return AssignNAC(
            op=op,
            dst=args[0] if len(args) > 0 else None,
            src=args[1] if len(args) > 1 else None,
            src2=args[2] if len(args) > 2 else None,
            **kw,
        )
    if nac_type == NAddressCodeType.UNCOND_JUMP:
        return UncondJumpNAC(target=args[0], **kw)
    if nac_type == NAddressCodeType.COND_JUMP:
        if len(args) == 3:
            return CondJumpNAC(op=op, cond1=args[0], cond2=args[1], target=args[2], **kw)
        return CondJumpNAC(op=op, cond1=args[0], target=args[1], **kw)
    if nac_type == NAddressCodeType.CALL:
        return CallNAC(
            dst=args[0] if len(args) > 0 else None,
            func=args[1] if len(args) > 1 else None,
            call_args=list(args[2:]) if len(args) > 2 else [],
            **kw,
        )
    if nac_type == NAddressCodeType.RETURN:
        return ReturnNAC(retval=args[0] if args else None, **kw)
    if nac_type == NAddressCodeType.UNCOND_THROW:
        return UncondThrowNAC(exception=args[0], **kw)
    if nac_type == NAddressCodeType.COND_THROW:
        return CondThrowNAC(op=op, cond1=args[0], cond2=args[1], exception=args[2], **kw)
    if nac_type == NAddressCodeType.IMPORT:
        return ImportNAC(imported=args[0], local_name=args[1], module=args[2], **kw)
    if nac_type == NAddressCodeType.VAR_DECL:
        return VarDeclNAC(var_names=list(args), **kw)
    # UNKNOWN (and any unrecognised type)
    return UnknownNAC(op=op, args=list(args), **kw)



