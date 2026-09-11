from decompile.ir.nac.types import NAddressCodeType


class NAddressCode:
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
        self.label_aliases = []
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
        labels = [*self.label_aliases]
        if self.label:
            labels.append(self.label)

        if labels:
            label_text = '\n'.join(f'{label}:' for label in labels)
            if self.comment:
                return f'{label_text}\n{nac_str}  /* {self.comment} */'
            else:
                return f'{label_text}\n{nac_str}'
        elif self.comment:
            return f'{nac_str}  /* {self.comment} */'
        else:
            return nac_str

    def __str__(self):
        raise NotImplementedError
