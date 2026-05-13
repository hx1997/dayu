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

    During the migration period each typed subclass stores ``self.args`` as the
    canonical mutable list and exposes named-field properties backed by it.
    Phase 9 will flip to named fields as canonical and drop the list.
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
        if src2 is not None:
            self.args = [dst, src, src2]
        else:
            self.args = [dst, src]

    # Named-field properties backed by self.args (the canonical list during migration)

    @property
    def dst(self):
        return self.args[0]

    @dst.setter
    def dst(self, value):
        self.args[0] = value

    @property
    def src(self):
        return self.args[1]

    @src.setter
    def src(self, value):
        self.args[1] = value

    @property
    def src2(self):
        return self.args[2] if len(self.args) > 2 else None

    @src2.setter
    def src2(self, value):
        if value is not None:
            if len(self.args) > 2:
                self.args[2] = value
            else:
                self.args.append(value)
        else:
            if len(self.args) > 2:
                self.args.pop()

    def get_defs(self):
        return [self.dst]

    def get_uses(self):
        uses = []
        if self.dst.ref_obj:
            uses.append(self.dst.ref_obj)
        uses.extend(self._arg_uses(self.src))
        if self.src2 is not None:
            uses.extend(self._arg_uses(self.src2))
        return uses

    def remap_args(self, fn):
        for i in range(len(self.args)):
            self.args[i] = fn(self.args[i])

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
        if len(self.args) == 3:
            s = f'{self.dst} = {self.src} {self.op} {self.src2}'
        else:
            s = f'{self.dst} = {self.op + (" " if self.op else "")}{self.src}'
        return self.format_nac_str_with_label(s)


class UncondJumpNAC(NACBase):
    """jump target"""

    type = NAddressCodeType.UNCOND_JUMP

    def __init__(self, target,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.args = [target]

    @property
    def target(self):
        return self.args[0]

    @target.setter
    def target(self, value):
        self.args[0] = value

    def get_uses(self):
        return self._arg_uses(self.target)

    def remap_args(self, fn):
        self.args[0] = fn(self.args[0])

    def __str__(self):
        return self.format_nac_str_with_label(f'jump {self.target}')


class CondJumpNAC(NACBase):
    """if (cond1) jump target  /  if (cond1 op cond2) jump target"""

    type = NAddressCodeType.COND_JUMP

    def __init__(self, op, cond1, target, cond2=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        if cond2 is not None:
            self.args = [cond1, cond2, target]
        else:
            self.args = [cond1, target]

    @property
    def cond1(self):
        return self.args[0]

    @cond1.setter
    def cond1(self, value):
        self.args[0] = value

    @property
    def cond2(self):
        return self.args[1] if len(self.args) == 3 else None

    @cond2.setter
    def cond2(self, value):
        if len(self.args) == 3:
            self.args[1] = value
        elif value is not None:
            # Promote from 2-arg to 3-arg form
            old_target = self.args[1]
            self.args = [self.args[0], value, old_target]

    @property
    def target(self):
        return self.args[-1]

    @target.setter
    def target(self, value):
        self.args[-1] = value

    def get_uses(self):
        uses = self._arg_uses(self.cond1)
        if self.cond2 is not None:
            uses.extend(self._arg_uses(self.cond2))
        # target is a label; include it for behavioural consistency with the old defuse.py
        uses.extend(self._arg_uses(self.target))
        return uses

    def remap_args(self, fn):
        for i in range(len(self.args)):
            self.args[i] = fn(self.args[i])

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
        if len(self.args) == 3:
            s = f'if ({self.cond1} {self.op} {self.cond2}) jump {self.target}'
        else:
            s = f'if ({self.cond1}) jump {self.target}'
        return self.format_nac_str_with_label(s)


class CallNAC(NACBase):
    """dst = func(call_args...)"""

    type = NAddressCodeType.CALL

    def __init__(self, func, call_args, dst=None,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.args = [dst, func, *call_args]

    @property
    def dst(self):
        return self.args[0]

    @dst.setter
    def dst(self, value):
        self.args[0] = value

    @property
    def func(self):
        return self.args[1]

    @func.setter
    def func(self, value):
        self.args[1] = value

    @property
    def call_args(self):
        return self.args[2:]

    @call_args.setter
    def call_args(self, value):
        self.args[2:] = value

    def get_defs(self):
        return [self.dst]

    def get_uses(self):
        uses = []
        if self.dst.ref_obj:
            uses.append(self.dst.ref_obj)
        uses.extend(self._arg_uses(self.func))
        for a in self.call_args:
            uses.extend(self._arg_uses(a))
        return uses

    def remap_args(self, fn):
        for i in range(len(self.args)):
            self.args[i] = fn(self.args[i])

    def __str__(self):
        call_args_str = [str(a) for a in self.call_args]
        return self.format_nac_str_with_label(
            f'{self.dst} = {self.func}({", ".join(call_args_str)})'
        )


class ReturnNAC(NACBase):
    """return retval"""

    type = NAddressCodeType.RETURN

    def __init__(self, retval,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.args = [retval]

    @property
    def retval(self):
        return self.args[0]

    @retval.setter
    def retval(self, value):
        self.args[0] = value

    def get_uses(self):
        return self._arg_uses(self.retval)

    def remap_args(self, fn):
        self.args[0] = fn(self.args[0])

    def __str__(self):
        return self.format_nac_str_with_label(f'return {self.retval}')


class UncondThrowNAC(NACBase):
    """throw exception"""

    type = NAddressCodeType.UNCOND_THROW

    def __init__(self, exception,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.args = [exception]

    @property
    def exception(self):
        return self.args[0]

    @exception.setter
    def exception(self, value):
        self.args[0] = value

    def get_uses(self):
        return self._arg_uses(self.exception)

    def remap_args(self, fn):
        self.args[0] = fn(self.args[0])

    def __str__(self):
        return self.format_nac_str_with_label(f'throw {self.exception}')


class CondThrowNAC(NACBase):
    """if (cond1 op cond2) throw exception"""

    type = NAddressCodeType.COND_THROW

    def __init__(self, op, cond1, cond2, exception,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.op = op
        self.args = [cond1, cond2, exception]

    @property
    def cond1(self):
        return self.args[0]

    @cond1.setter
    def cond1(self, value):
        self.args[0] = value

    @property
    def cond2(self):
        return self.args[1]

    @cond2.setter
    def cond2(self, value):
        self.args[1] = value

    @property
    def exception(self):
        return self.args[2]

    @exception.setter
    def exception(self, value):
        self.args[2] = value

    def get_uses(self):
        uses = []
        for a in [self.cond1, self.cond2, self.exception]:
            uses.extend(self._arg_uses(a))
        return uses

    def remap_args(self, fn):
        for i in range(3):
            self.args[i] = fn(self.args[i])

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
        s = f'if ({self.cond1} {self.op} {self.cond2}) throw {self.exception}'
        return self.format_nac_str_with_label(s)


class ImportNAC(NACBase):
    """import { imported } as local_name from 'module'"""

    type = NAddressCodeType.IMPORT

    def __init__(self, imported, local_name, module,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.args = [imported, local_name, module]

    @property
    def imported(self):
        return self.args[0]

    @imported.setter
    def imported(self, value):
        self.args[0] = value

    @property
    def local_name(self):
        return self.args[1]

    @local_name.setter
    def local_name(self, value):
        self.args[1] = value

    @property
    def module(self):
        return self.args[2]

    @module.setter
    def module(self, value):
        self.args[2] = value

    def remap_args(self, fn):
        for i in range(3):
            self.args[i] = fn(self.args[i])

    def __str__(self):
        s = ('import { ' + f'{self.imported}' + ' } as '
             + f"{self.local_name} from '{self.module}';")
        return self.format_nac_str_with_label(s)


class VarDeclNAC(NACBase):
    """let var1, var2, ..."""

    type = NAddressCodeType.VAR_DECL

    def __init__(self, var_names,
                 parent_block=None, label_name='', comment='', extra_info=None):
        super().__init__(parent_block=parent_block, label_name=label_name,
                         comment=comment, extra_info=extra_info)
        self.args = list(var_names)

    @property
    def var_names(self):
        return self.args

    @var_names.setter
    def var_names(self, value):
        self.args[:] = value

    def remap_args(self, fn):
        for i in range(len(self.args)):
            self.args[i] = fn(self.args[i])

    def __str__(self):
        return self.format_nac_str_with_label(
            f'let {", ".join([str(a) for a in self.var_names])}'
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



